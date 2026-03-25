"""
Project context management
Used to persist project state server-side, avoiding large data passing between front-end APIs
"""

import os
import json
import uuid
import shutil
from datetime import datetime
from typing import Dict, Any, List, Optional
from enum import Enum
from dataclasses import dataclass, field, asdict
from ..config import Config


class ProjectStatus(str, Enum):
    """Project state"""
    CREATED = "created"              # Created, files uploaded
    ONTOLOGY_GENERATED = "ontology_generated"  # Ontology generated
    GRAPH_BUILDING = "graph_building"    # Graph building
    GRAPH_COMPLETED = "graph_completed"  # Graph completed
    FAILED = "failed"                # Failed


@dataclass
class Project:
    """Project data model"""
    project_id: str
    name: str
    status: ProjectStatus
    created_at: str
    updated_at: str
    
    # File info
    files: List[Dict[str, str]] = field(default_factory=list)  # [{filename, path, size}]
    total_text_length: int = 0
    
    # Ontology info (filled after interface 1 generates)
    ontology: Optional[Dict[str, Any]] = None
    analysis_summary: Optional[str] = None
    
    # Graph info (filled after interface 2 completes)
    graph_id: Optional[str] = None
    graph_build_task_id: Optional[str] = None
    
    # Config
    simulation_requirement: Optional[str] = None
    chunk_size: int = 500
    chunk_overlap: int = 50
    
    # Error message
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict"""
        return {
            "project_id": self.project_id,
            "name": self.name,
            "status": self.status.value if isinstance(self.status, ProjectStatus) else self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "files": self.files,
            "total_text_length": self.total_text_length,
            "ontology": self.ontology,
            "analysis_summary": self.analysis_summary,
            "graph_id": self.graph_id,
            "graph_build_task_id": self.graph_build_task_id,
            "simulation_requirement": self.simulation_requirement,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "error": self.error
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Project':
        """Create from dict"""
        status = data.get('status', 'created')
        if isinstance(status, str):
            status = ProjectStatus(status)
        
        return cls(
            project_id=data['project_id'],
            name=data.get('name', 'Unnamed Project'),
            status=status,
            created_at=data.get('created_at', ''),
            updated_at=data.get('updated_at', ''),
            files=data.get('files', []),
            total_text_length=data.get('total_text_length', 0),
            ontology=data.get('ontology'),
            analysis_summary=data.get('analysis_summary'),
            graph_id=data.get('graph_id'),
            graph_build_task_id=data.get('graph_build_task_id'),
            simulation_requirement=data.get('simulation_requirement'),
            chunk_size=data.get('chunk_size', 500),
            chunk_overlap=data.get('chunk_overlap', 50),
            error=data.get('error')
        )


class ProjectManager:
    """Project Manager - responsible for persistent storage and retrieval of projects"""
    
    # Project storage root directory
    PROJECTS_DIR = os.path.join(Config.UPLOAD_FOLDER, 'projects')
    
    @classmethod
    def _ensure_projects_dir(cls):
        """Ensure project directory exists"""
        os.makedirs(cls.PROJECTS_DIR, exist_ok=True)
    
    @classmethod
    def _get_project_dir(cls, project_id: str) -> str:
        """Get project directory path"""
        return os.path.join(cls.PROJECTS_DIR, project_id)
    
    @classmethod
    def _get_project_meta_path(cls, project_id: str) -> str:
        """Get project metadata file path"""
        return os.path.join(cls._get_project_dir(project_id), 'project.json')
    
    @classmethod
    def _get_project_files_dir(cls, project_id: str) -> str:
        """Get project file storage directory"""
        return os.path.join(cls._get_project_dir(project_id), 'files')
    
    @classmethod
    def _get_project_text_path(cls, project_id: str) -> str:
        """Get project extracted text storage path"""
        return os.path.join(cls._get_project_dir(project_id), 'extracted_text.txt')
    
    @classmethod
    def create_project(cls, name: str = "Unnamed Project") -> Project:
        """
        Create new project
        
        Args:
            name: Project name
            
        Returns:
            Newly created Project object
        """
        cls._ensure_projects_dir()
        
        project_id = f"proj_{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()
        
        project = Project(
            project_id=project_id,
            name=name,
            status=ProjectStatus.CREATED,
            created_at=now,
            updated_at=now
        )
        
        # Create project directory structure
        project_dir = cls._get_project_dir(project_id)
        files_dir = cls._get_project_files_dir(project_id)
        os.makedirs(project_dir, exist_ok=True)
        os.makedirs(files_dir, exist_ok=True)
        
        # Save project metadata
        cls.save_project(project)
        
        return project
    
    @classmethod
    def save_project(cls, project: Project) -> None:
        """Save project metadata"""
        project.updated_at = datetime.now().isoformat()
        meta_path = cls._get_project_meta_path(project.project_id)
        
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(project.to_dict(), f, ensure_ascii=False, indent=2)
    
    @classmethod
    def get_project(cls, project_id: str) -> Optional[Project]:
        """
        Get project
        
        Args:
            project_id: Project ID
            
        Returns:
            Project object, return None if not exists
        """
        meta_path = cls._get_project_meta_path(project_id)
        
        if not os.path.exists(meta_path):
            return None
        
        with open(meta_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return Project.from_dict(data)
    
    @classmethod
    def list_projects(cls, limit: int = 50) -> List[Project]:
        """
        List all projects
        
        Args:
            limit: Return quantity limit
            
        Returns:
            Project list, sorted descending by creation time
        """
        cls._ensure_projects_dir()
        
        projects = []
        for project_id in os.listdir(cls.PROJECTS_DIR):
            project = cls.get_project(project_id)
            if project:
                projects.append(project)
        
        # Sort descending by creation time
        projects.sort(key=lambda p: p.created_at, reverse=True)
        
        return projects[:limit]
    
    @classmethod
    def delete_project(cls, project_id: str) -> bool:
        """
        Delete project and all its files
        
        Args:
            project_id: Project ID
            
        Returns:
            Whether deletion successful
        """
        project_dir = cls._get_project_dir(project_id)
        
        if not os.path.exists(project_dir):
            return False
        
        shutil.rmtree(project_dir)
        return True
    
    @classmethod
    def save_file_to_project(cls, project_id: str, file_storage, original_filename: str) -> Dict[str, str]:
        """
        Save uploaded files to project directory
        
        Args:
            project_id: Project ID
            file_storage: Flask FileStorage object
            original_filename: Original filename
            
        Returns:
            File info dict {filename, path, size}
        """
        files_dir = cls._get_project_files_dir(project_id)
        os.makedirs(files_dir, exist_ok=True)
        
        # Generate secure filename
        ext = os.path.splitext(original_filename)[1].lower()
        safe_filename = f"{uuid.uuid4().hex[:8]}{ext}"
        file_path = os.path.join(files_dir, safe_filename)
        
        # Save file
        file_storage.save(file_path)
        
        # Get file size
        file_size = os.path.getsize(file_path)
        
        return {
            "original_filename": original_filename,
            "saved_filename": safe_filename,
            "path": file_path,
            "size": file_size
        }
    
    @classmethod
    def save_extracted_text(cls, project_id: str, text: str) -> None:
        """Save extracted text"""
        text_path = cls._get_project_text_path(project_id)
        with open(text_path, 'w', encoding='utf-8') as f:
            f.write(text)
    
    @classmethod
    def get_extracted_text(cls, project_id: str) -> Optional[str]:
        """Get extracted text"""
        text_path = cls._get_project_text_path(project_id)
        
        if not os.path.exists(text_path):
            return None
        
        with open(text_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    @classmethod
    def find_project_by_graph_id(cls, graph_id: str) -> Optional[Project]:
        """Find project by graph_id"""
        cls._ensure_projects_dir()
        for project_id in os.listdir(cls.PROJECTS_DIR):
            project = cls.get_project(project_id)
            if project and project.graph_id == graph_id:
                return project
        return None

    @classmethod
    def save_graph_cache(cls, project_id: str, graph_data: Dict[str, Any]) -> None:
        """Save graph data (nodes/edges) to local cache file"""
        from datetime import datetime as _dt
        cache_path = os.path.join(cls._get_project_dir(project_id), 'graph_data.json')
        graph_data['cached_at'] = _dt.now().isoformat()
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(graph_data, f, ensure_ascii=False, indent=2)

    @classmethod
    def get_graph_cache(cls, graph_id: str) -> Optional[Dict[str, Any]]:
        """Return cached graph data for a graph_id, or None if not cached"""
        project = cls.find_project_by_graph_id(graph_id)
        if not project:
            return None
        cache_path = os.path.join(cls._get_project_dir(project.project_id), 'graph_data.json')
        if not os.path.exists(cache_path):
            return None
        with open(cache_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    @classmethod
    def get_project_files(cls, project_id: str) -> List[str]:
        """Get all file paths for project"""
        files_dir = cls._get_project_files_dir(project_id)
        
        if not os.path.exists(files_dir):
            return []
        
        return [
            os.path.join(files_dir, f) 
            for f in os.listdir(files_dir) 
            if os.path.isfile(os.path.join(files_dir, f))
        ]

