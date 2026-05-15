"""
Data Ingestion API Routes - Extract Twitter/News data and prepare for simulation
FASE 0: Data Collection and Profile Selection
"""

import uuid
import asyncio
from typing import Optional, Dict, Any
from flask import request, jsonify, current_app, Blueprint
from . import graph_bp  # Reuse graph blueprint for consistency
from ..data_extraction import TwitterExtractor, NewsExtractor

data_ingestion_bp = Blueprint('data_ingestion', __name__)
from ..models.data_extraction import (
    TwitterExtractionRequest,
    TwitterExtractionResponse,
    NewsExtractionRequest,
    NewsExtractionResponse,
    SimulationDataPackage,
    SelectedProfile
)
from ..utils.logger import get_logger
from ..config import Config

logger = get_logger('mirofish.api.data_ingestion')

# Job storage (in production, use Redis or database)
extraction_jobs: Dict[str, Dict[str, Any]] = {}


def _get_storage():
    """Get Neo4jStorage from Flask app extensions"""
    storage = current_app.extensions.get('neo4j_storage')
    if not storage:
        raise ValueError("Neo4jStorage not initialized")
    return storage


# ============== Twitter Extraction Endpoints ==============

@data_ingestion_bp.route('/extract/twitter', methods=['POST'])
def extract_twitter():
    """
    Extract Twitter/X profile and tweet data
    
    Request:
    {
        "query": "elonmusk",
        "extract_type": "profile",  # or "search"
        "limit": 10,
        "include_tweets": true
    }
    
    Response:
    {
        "success": true,
        "extraction_id": "ext_abc123",
        "status": "processing",
        "profiles": [...],
        "tweets": [...]
    }
    """
    try:
        req = TwitterExtractionRequest(**request.get_json())
        
        # Generate unique extraction ID
        extraction_id = f"tw_{uuid.uuid4().hex[:8]}"
        
        # Initialize job
        extraction_jobs[extraction_id] = {
            'status': 'processing',
            'type': 'twitter',
            'request': req.dict(),
            'profiles': [],
            'tweets': [],
            'error': None
        }
        
        logger.info(f"Started extraction {extraction_id}: {req.query}")
        
        # Run extraction async
        def run_extraction():
            try:
                extractor = TwitterExtractor(
                    ollama_base_url=Config.LLM_BASE_URL,
                    model=Config.LLM_MODEL_NAME
                )
                
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    if req.extract_type == 'profile':
                        # Single profile extraction
                        profile = loop.run_until_complete(
                            extractor.extract_profile(req.query)
                        )
                        if profile:
                            extraction_jobs[extraction_id]['profiles'].append(profile.dict())
                        
                        if req.include_tweets:
                            tweets = loop.run_until_complete(
                                extractor.extract_tweets(req.query, limit=req.limit)
                            )
                            extraction_jobs[extraction_id]['tweets'] = [
                                t.dict() for t in tweets
                            ]
                    
                    elif req.extract_type == 'search':
                        # Search and extract
                        results = loop.run_until_complete(
                            extractor.extract_search_results(req.query, limit=req.limit)
                        )
                        extraction_jobs[extraction_id]['profiles'] = results.get('top_profiles', [])
                        extraction_jobs[extraction_id]['tweets'] = results.get('relevant_tweets', [])
                    
                    extraction_jobs[extraction_id]['status'] = 'completed'
                
                finally:
                    loop.close()
            
            except Exception as e:
                logger.error(f"Extraction {extraction_id} failed: {str(e)}")
                extraction_jobs[extraction_id]['status'] = 'failed'
                extraction_jobs[extraction_id]['error'] = str(e)
        
        # Start async thread
        import threading
        thread = threading.Thread(target=run_extraction, daemon=True)
        thread.start()
        
        return jsonify({
            'success': True,
            'extraction_id': extraction_id,
            'status': 'processing',
            'message': f'Extraction started for: {req.query}'
        }), 202
    
    except Exception as e:
        logger.error(f"Extract Twitter error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@data_ingestion_bp.route('/extract/twitter/<extraction_id>', methods=['GET'])
def get_twitter_extraction(extraction_id: str):
    """
    Get Twitter extraction status and results
    
    Response:
    {
        "success": true,
        "status": "completed",
        "profiles": [...],
        "tweets": [...]
    }
    """
    if extraction_id not in extraction_jobs:
        return jsonify({
            'success': False,
            'error': 'Extraction not found'
        }), 404
    
    job = extraction_jobs[extraction_id]
    
    return jsonify({
        'success': job['status'] != 'failed',
        'status': job['status'],
        'profiles': job['profiles'],
        'tweets': job['tweets'],
        'error': job.get('error')
    })


# ============== News Extraction Endpoints ==============

@data_ingestion_bp.route('/extract/news', methods=['POST'])
def extract_news():
    """
    Extract financial news articles
    
    Request:
    {
        "query": "Fed interest rates",
        "sources": ["Reuters", "Bloomberg"],
        "time_range": "7d",
        "limit": 10
    }
    
    Response:
    {
        "success": true,
        "extraction_id": "news_abc123",
        "status": "processing",
        "articles": [...]
    }
    """
    try:
        req = NewsExtractionRequest(**request.get_json())
        
        extraction_id = f"news_{uuid.uuid4().hex[:8]}"
        
        extraction_jobs[extraction_id] = {
            'status': 'processing',
            'type': 'news',
            'request': req.dict(),
            'articles': [],
            'error': None
        }
        
        logger.info(f"Started news extraction {extraction_id}: {req.query}")
        
        def run_extraction():
            try:
                extractor = NewsExtractor(timeout=30)
                
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    articles = loop.run_until_complete(
                        extractor.search_news(
                            query=req.query,
                            source_filter=req.sources,
                            time_range=req.time_range,
                            limit=req.limit
                        )
                    )
                    
                    extraction_jobs[extraction_id]['articles'] = [
                        a.dict() for a in articles
                    ]
                    extraction_jobs[extraction_id]['status'] = 'completed'
                
                finally:
                    loop.close()
            
            except Exception as e:
                logger.error(f"News extraction {extraction_id} failed: {str(e)}")
                extraction_jobs[extraction_id]['status'] = 'failed'
                extraction_jobs[extraction_id]['error'] = str(e)
        
        import threading
        thread = threading.Thread(target=run_extraction, daemon=True)
        thread.start()
        
        return jsonify({
            'success': True,
            'extraction_id': extraction_id,
            'status': 'processing',
            'message': f'News extraction started for: {req.query}'
        }), 202
    
    except Exception as e:
        logger.error(f"Extract news error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@data_ingestion_bp.route('/extract/news/<extraction_id>', methods=['GET'])
def get_news_extraction(extraction_id: str):
    """Get news extraction status and results"""
    if extraction_id not in extraction_jobs:
        return jsonify({
            'success': False,
            'error': 'Extraction not found'
        }), 404
    
    job = extraction_jobs[extraction_id]
    
    return jsonify({
        'success': job['status'] != 'failed',
        'status': job['status'],
        'articles': job['articles'],
        'error': job.get('error')
    })


# ============== Data Selection and Simulation Package ==============

@data_ingestion_bp.route('/prepare-simulation-package', methods=['POST'])
def prepare_simulation_package():
    """
    Select profiles and articles for simulation
    Creates final data package ready for Graph Build (Step 1)
    
    Request:
    {
        "selected_profile_ids": ["username1", "username2"],
        "selected_article_ids": ["article_url_1"],
        "simulation_config": {
            "duration": 100,
            "interval": 1
        }
    }
    
    Response:
    {
        "success": true,
        "package_id": "pkg_abc123",
        "profiles": [...],
        "articles": [...]
    }
    """
    try:
        data = request.get_json()
        
        package_id = f"pkg_{uuid.uuid4().hex[:8]}"
        
        # Collect selected profiles from recent extractions
        selected_profiles = []
        selected_articles = []
        
        # TODO: Implement profile/article filtering logic
        # For now, just create empty package structure
        
        package = SimulationDataPackage(
            session_id=package_id,
            profiles=selected_profiles,
            articles=selected_articles,
            simulation_config=data.get('simulation_config', {})
        )
        
        logger.info(f"Created simulation package {package_id}")
        
        return jsonify({
            'success': True,
            'package_id': package_id,
            'profiles': [p.dict() for p in package.profiles],
            'articles': [a.dict() for a in package.articles]
        })
    
    except Exception as e:
        logger.error(f"Prepare simulation package error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@data_ingestion_bp.route('/clear-extractions', methods=['POST'])
def clear_extractions():
    """Clear all cached extractions (for testing/cleanup)"""
    global extraction_jobs
    count = len(extraction_jobs)
    extraction_jobs = {}
    
    return jsonify({
        'success': True,
        'cleared': count
    })