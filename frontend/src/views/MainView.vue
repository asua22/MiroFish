<template>
  <div class="main-view">
    <!-- Header -->
    <header class="app-header">
      <div class="header-left">
        <div class="brand" @click="router.push('/')">MIROFISH OFFLINE</div>
      </div>

      <div class="header-center">
        <div class="view-switcher">
          <button
            v-for="mode in ['graph', 'split', 'workbench']"
            :key="mode"
            class="switch-btn"
            :class="{ active: viewMode === mode }"
            @click="viewMode = mode"
          >
            {{
              { graph: "Graph", split: "Split", workbench: "Workbench" }[mode]
            }}
          </button>
        </div>
      </div>

      <div class="header-right">
        <div class="workflow-step">
          <!-- Modificado para mostrar Step X/6 basado en índice 0 -->
          <span class="step-num">Step {{ currentStep + 1 }}/6</span>
          <span class="step-name">{{ stepNames[currentStep] }}</span>
        </div>
        <div class="step-divider"></div>
        <span class="status-indicator" :class="statusClass">
          <span class="dot"></span>
          {{ statusText }}
        </span>
      </div>
    </header>

    <!-- Main Content Area -->
    <main class="content-area">
      <!-- Left Panel: Graph -->
      <div class="panel-wrapper left" :style="leftPanelStyle">
        <GraphPanel
          :graphData="graphData"
          :loading="graphLoading"
          :currentPhase="currentPhase"
          @refresh="refreshGraph"
          @toggle-maximize="toggleMaximize('graph')"
        />
      </div>

      <!-- Right Panel: Step Components -->
      <div class="panel-wrapper right" :style="rightPanelStyle">
        <!-- NUEVO: Step 0: Data Ingestion -->
        <Step0DataIngestion
          v-if="currentStep === 0"
          :projectData="projectData"
          @next-step="handleNextStep"
          @data-selected="onDataSelected"
        />

        <!-- Step 1: Graph Build (Ahora condicionado a currentStep 1) -->
        <Step1GraphBuild
          v-else-if="currentStep === 1"
          :currentPhase="currentPhase"
          :projectData="projectData"
          :selectedData="selectedData"
          :ontologyProgress="ontologyProgress"
          :buildProgress="buildProgress"
          :graphData="graphData"
          :systemLogs="systemLogs"
          @next-step="handleNextStep"
        />

        <!-- Step 2: Env Setup (Ahora condicionado a currentStep 2) -->
        <Step2EnvSetup
          v-else-if="currentStep === 2"
          :projectData="projectData"
          :graphData="graphData"
          :systemLogs="systemLogs"
          @go-back="handleGoBack"
          @next-step="handleNextStep"
          @add-log="addLog"
        />
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from "vue";
import { useRoute, useRouter } from "vue-router";

// Componentes
import GraphPanel from "../components/GraphPanel.vue";
import Step0DataIngestion from "../components/Step0DataIngestion.vue"; // Nuevo
import Step1GraphBuild from "../components/Step1GraphBuild.vue";
import Step2EnvSetup from "../components/Step2EnvSetup.vue";

// API
import {
  generateOntology,
  getProject,
  buildGraph,
  getTaskStatus,
  getGraphData,
} from "../api/graph";
import { getPendingUpload, clearPendingUpload } from "../store/pendingUpload";

const route = useRoute();
const router = useRouter();

// Layout State
const viewMode = ref("split"); // graph | split | workbench

// --- Step State Modificado ---
const currentStep = ref(0); // 0: Data Ingestion, 1: Graph Build, 2: Env Setup, etc.
const stepNames = [
  "Data Ingestion",
  "Graph Build",
  "Env Setup",
  "Simulation",
  "Report",
  "Interaction",
];

// Data State
const currentProjectId = ref(route.params.projectId);
const loading = ref(false);
const graphLoading = ref(false);
const error = ref("");
const projectData = ref(null);
const graphData = ref(null);
const currentPhase = ref(-1); // -1: Upload, 0: Ontology, 1: Build, 2: Complete
const ontologyProgress = ref(null);
const buildProgress = ref(null);
const systemLogs = ref([]);

// NUEVO: Almacenamiento de datos extraídos en Fase 0
const selectedData = ref(null);

// Polling timers
let pollTimer = null;
let graphPollTimer = null;

// --- Computed Layout Styles ---
const leftPanelStyle = computed(() => {
  if (viewMode.value === "graph")
    return { width: "100%", opacity: 1, transform: "translateX(0)" };
  if (viewMode.value === "workbench")
    return { width: "0%", opacity: 0, transform: "translateX(-20px)" };
  return { width: "50%", opacity: 1, transform: "translateX(0)" };
});

const rightPanelStyle = computed(() => {
  if (viewMode.value === "workbench")
    return { width: "100%", opacity: 1, transform: "translateX(0)" };
  if (viewMode.value === "graph")
    return { width: "0%", opacity: 0, transform: "translateX(20px)" };
  return { width: "50%", opacity: 1, transform: "translateX(0)" };
});

// --- Status Computed ---
const statusClass = computed(() => {
  if (error.value) return "error";
  if (currentPhase.value >= 2) return "completed";
  return "processing";
});

const statusText = computed(() => {
  if (error.value) return "Error";
  if (currentPhase.value >= 2) return "Ready";
  if (currentPhase.value === 1) return "Building Graph";
  if (currentPhase.value === 0) return "Generating Ontology";
  return "Initializing";
});

// --- Helpers ---
const addLog = (msg) => {
  const time =
    new Date().toLocaleTimeString("en-US", {
      hour12: false,
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }) +
    "." +
    new Date().getMilliseconds().toString().padStart(3, "0");
  systemLogs.value.push({ time, msg });
  if (systemLogs.value.length > 100) {
    systemLogs.value.shift();
  }
};

// --- Layout Methods ---
const toggleMaximize = (target) => {
  viewMode.value = viewMode.value === target ? "split" : target;
};

// --- Handlers Fase 0 ---
const onDataSelected = (data) => {
  selectedData.value = data;
  addLog(
    "Data selected from Ingestion Phase: Twitter profiles and News context stored.",
  );
};

const handleNextStep = (params = {}) => {
  if (currentStep.value < 5) {
    currentStep.value++;
    addLog(
      `Entering Step ${currentStep.value + 1}: ${stepNames[currentStep.value]}`,
    );

    if (currentStep.value === 3 && params.maxRounds) {
      addLog(`Custom simulation rounds: ${params.maxRounds}`);
    }
  }
};

const handleGoBack = () => {
  if (currentStep.value > 0) {
    currentStep.value--;
    addLog(
      `Back to Step ${currentStep.value + 1}: ${stepNames[currentStep.value]}`,
    );
  }
};

// --- Data Logic ---

const initProject = async () => {
  addLog("Project view initialized.");
  if (currentProjectId.value === "new") {
    await handleNewProject();
  } else {
    await loadProject();
  }
};

const handleNewProject = async () => {
  const pending = getPendingUpload();
  if (!pending.isPending || pending.files.length === 0) {
    error.value = "No pending files found.";
    addLog("Error: No pending files found for new project.");
    return;
  }

  try {
    loading.value = true;
    currentPhase.value = 0;
    ontologyProgress.value = { message: "Uploading and analyzing docs..." };
    addLog("Starting ontology generation: Uploading files...");

    const formData = new FormData();
    pending.files.forEach((f) => formData.append("files", f));
    formData.append("simulation_requirement", pending.simulationRequirement);

    const res = await generateOntology(formData);
    if (res.success) {
      clearPendingUpload();
      currentProjectId.value = res.data.project_id;
      projectData.value = res.data;

      router.replace({
        name: "Process",
        params: { projectId: res.data.project_id },
      });
      ontologyProgress.value = null;
      addLog(
        `Ontology generated successfully for project ${res.data.project_id}`,
      );
      await startBuildGraph();
    } else {
      error.value = res.error || "Ontology generation failed";
      addLog(`Error generating ontology: ${error.value}`);
    }
  } catch (err) {
    error.value = err.message;
    addLog(`Exception in handleNewProject: ${err.message}`);
  } finally {
    loading.value = false;
  }
};

const loadProject = async () => {
  try {
    loading.value = true;
    addLog(`Loading project ${currentProjectId.value}...`);
    const res = await getProject(currentProjectId.value);
    if (res.success) {
      projectData.value = res.data;
      updatePhaseByStatus(res.data.status);
      addLog(`Project loaded. Status: ${res.data.status}`);

      if (res.data.status === "ontology_generated" && !res.data.graph_id) {
        await startBuildGraph();
      } else if (
        res.data.status === "graph_building" &&
        res.data.graph_build_task_id
      ) {
        currentPhase.value = 1;
        startPollingTask(res.data.graph_build_task_id);
        startGraphPolling();
      } else if (res.data.status === "graph_completed" && res.data.graph_id) {
        currentPhase.value = 2;
        await loadGraph(res.data.graph_id);
      }
    } else {
      error.value = res.error;
      addLog(`Error loading project: ${res.error}`);
    }
  } catch (err) {
    error.value = err.message;
    addLog(`Exception in loadProject: ${err.message}`);
  } finally {
    loading.value = false;
  }
};

const updatePhaseByStatus = (status) => {
  switch (status) {
    case "created":
    case "ontology_generated":
      currentPhase.value = 0;
      break;
    case "graph_building":
      currentPhase.value = 1;
      break;
    case "graph_completed":
      currentPhase.value = 2;
      break;
    case "failed":
      error.value = "Project failed";
      break;
  }
};

const startBuildGraph = async () => {
  try {
    currentPhase.value = 1;
    buildProgress.value = { progress: 0, message: "Starting build..." };
    addLog("Initiating graph build...");

    const res = await buildGraph({ project_id: currentProjectId.value });
    if (res.success) {
      addLog(`Graph build task started. Task ID: ${res.data.task_id}`);
      startGraphPolling();
      startPollingTask(res.data.task_id);
    } else {
      error.value = res.error;
      addLog(`Error starting build: ${res.error}`);
    }
  } catch (err) {
    error.value = err.message;
    addLog(`Exception in startBuildGraph: ${err.message}`);
  }
};

const startGraphPolling = () => {
  addLog("Started polling for graph data...");
  fetchGraphData();
  graphPollTimer = setInterval(fetchGraphData, 10000);
};

const fetchGraphData = async () => {
  try {
    const projRes = await getProject(currentProjectId.value);
    if (projRes.success && projRes.data.graph_id) {
      const gRes = await getGraphData(projRes.data.graph_id);
      if (gRes.success) {
        graphData.value = gRes.data;
        const nodeCount = gRes.data.node_count || gRes.data.nodes?.length || 0;
        const edgeCount = gRes.data.edge_count || gRes.data.edges?.length || 0;
        addLog(
          `Graph data refreshed. Nodes: ${nodeCount}, Edges: ${edgeCount}`,
        );
      }
    }
  } catch (err) {
    console.warn("Graph fetch error:", err);
  }
};

const startPollingTask = (taskId) => {
  pollTaskStatus(taskId);
  pollTimer = setInterval(() => pollTaskStatus(taskId), 2000);
};

const pollTaskStatus = async (taskId) => {
  try {
    const res = await getTaskStatus(taskId);
    if (res.success) {
      const task = res.data;

      if (task.message && task.message !== buildProgress.value?.message) {
        addLog(task.message);
      }

      buildProgress.value = {
        progress: task.progress || 0,
        message: task.message,
      };

      if (task.status === "completed") {
        addLog("Graph build task completed.");
        stopPolling();
        stopGraphPolling();
        currentPhase.value = 2;

        const projRes = await getProject(currentProjectId.value);
        if (projRes.success && projRes.data.graph_id) {
          projectData.value = projRes.data;
          await loadGraph(projRes.data.graph_id);
        }
      } else if (task.status === "failed") {
        stopPolling();
        error.value = task.error;
        addLog(`Graph build task failed: ${task.error}`);
      }
    }
  } catch (e) {
    console.error(e);
  }
};

const loadGraph = async (graphId) => {
  graphLoading.value = true;
  addLog(`Loading full graph data: ${graphId}`);
  try {
    const res = await getGraphData(graphId);
    if (res.success) {
      graphData.value = res.data;
      addLog("Graph data loaded successfully.");
    } else {
      addLog(`Failed to load graph data: ${res.error}`);
    }
  } catch (e) {
    addLog(`Exception loading graph: ${e.message}`);
  } finally {
    graphLoading.value = false;
  }
};

const refreshGraph = () => {
  if (projectData.value?.graph_id) {
    addLog("Manual graph refresh triggered.");
    loadGraph(projectData.value.graph_id);
  }
};

const stopPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
};

const stopGraphPolling = () => {
  if (graphPollTimer) {
    clearInterval(graphPollTimer);
    graphPollTimer = null;
    addLog("Graph polling stopped.");
  }
};

onMounted(() => {
  initProject();
});

onUnmounted(() => {
  stopPolling();
  stopGraphPolling();
});
</script>

<style scoped>
.main-view {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #fff;
  overflow: hidden;
  font-family: "Space Grotesk", "Noto Sans SC", system-ui, sans-serif;
}

/* Header */
.app-header {
  height: 60px;
  border-bottom: 1px solid #eaeaea;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  background: #fff;
  z-index: 100;
  position: relative;
}

.header-center {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
}

.brand {
  font-family: "JetBrains Mono", monospace;
  font-weight: 800;
  font-size: 18px;
  letter-spacing: 1px;
  cursor: pointer;
}

.view-switcher {
  display: flex;
  background: #f5f5f5;
  padding: 4px;
  border-radius: 6px;
  gap: 4px;
}

.switch-btn {
  border: none;
  background: transparent;
  padding: 6px 16px;
  font-size: 12px;
  font-weight: 600;
  color: #666;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}

.switch-btn.active {
  background: #fff;
  color: #000;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #666;
  font-weight: 500;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.workflow-step {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
}

.step-num {
  font-family: "JetBrains Mono", monospace;
  font-weight: 700;
  color: #999;
}

.step-name {
  font-weight: 700;
  color: #000;
}

.step-divider {
  width: 1px;
  height: 14px;
  background-color: #e0e0e0;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #ccc;
}

.status-indicator.processing .dot {
  background: #ff5722;
  animation: pulse 1s infinite;
}
.status-indicator.completed .dot {
  background: #4caf50;
}
.status-indicator.error .dot {
  background: #f44336;
}

@keyframes pulse {
  50% {
    opacity: 0.5;
  }
}

/* Content */
.content-area {
  flex: 1;
  display: flex;
  position: relative;
  overflow: hidden;
}

.panel-wrapper {
  height: 100%;
  overflow: hidden;
  transition:
    width 0.4s cubic-bezier(0.25, 0.8, 0.25, 1),
    opacity 0.3s ease,
    transform 0.3s ease;
  will-change: width, opacity, transform;
}

.panel-wrapper.left {
  border-right: 1px solid #eaeaea;
}
</style>
