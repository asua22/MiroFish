<template>
  <div v-if="showStatus" class="extraction-status">
    <div class="status-header">
      <div class="status-indicator" :class="`status-${status}`">
        <span v-if="status === 'processing'" class="spinner"></span>
        <span v-else-if="status === 'completed'" class="icon">✓</span>
        <span v-else-if="status === 'failed'" class="icon">✕</span>
      </div>

      <div class="status-text">
        <p class="status-label">
          {{ statusLabel }}
        </p>
        <p class="status-description">
          {{ statusDescription }}
        </p>
      </div>

      <button class="close-btn" @click="showStatus = false">×</button>
    </div>

    <!-- Progress Bar -->
    <div v-if="status === 'processing'" class="progress-bar">
      <div class="progress-fill"></div>
    </div>

    <!-- Results Summary -->
    <div v-if="status === 'completed' && data" class="results-summary">
      <div class="summary-items">
        <div class="summary-item">
          <span class="item-icon">📊</span>
          <div>
            <p class="item-label">Data Extracted</p>
            <p class="item-value">{{ itemCount }} items</p>
          </div>
        </div>
        <div class="summary-item">
          <span class="item-icon">⏱️</span>
          <div>
            <p class="item-label">Time</p>
            <p class="item-value">{{ extractionTime }}s</p>
          </div>
        </div>
      </div>
    </div>

    <!-- Error Details -->
    <div v-if="status === 'failed'" class="error-details">
      <p v-if="data?.error" class="error-text">{{ data.error }}</p>
      <p v-else class="error-text">Extraction failed. Please try again.</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from "vue";
import axios from "axios";

const props = defineProps({
  extractionId: {
    type: String,
    required: true,
  },
  endpoint: {
    type: String,
    required: true,
  },
});

const emit = defineEmits(["loaded", "error"]);

// State
const showStatus = ref(true);
const status = ref("processing"); // processing, completed, failed
const data = ref(null);
const startTime = ref(Date.now());
const pollTimer = ref(null);

// Computed
const statusLabel = computed(() => {
  const labels = {
    processing: "Extracting data...",
    completed: "Extraction completed!",
    failed: "Extraction failed",
  };
  return labels[status.value] || "Processing";
});

const statusDescription = computed(() => {
  const descriptions = {
    processing: "This may take 30-90 seconds depending on data size",
    completed: "Data is ready for review and selection",
    failed: "There was an error during extraction",
  };
  return descriptions[status.value] || "";
});

const extractionTime = computed(() => {
  if (data.value?.extractedAt) {
    return Math.round((Date.now() - startTime.value) / 1000);
  }
  return 0;
});

const itemCount = computed(() => {
  if (data.value?.profiles) return data.value.profiles.length;
  if (data.value?.articles) return data.value.articles.length;
  return 0;
});

// Methods
const pollStatus = async () => {
  try {
    const response = await axios.get(props.endpoint);
    const result = response.data;

    status.value = result.status;

    if (result.status === "completed") {
      data.value = result;
      emit("loaded", result);
      stopPolling();
    } else if (result.status === "failed") {
      data.value = result;
      emit("error", result);
      stopPolling();
    }
  } catch (error) {
    console.error("Error polling extraction status:", error);
    status.value = "failed";
    emit("error", { error: "Failed to check extraction status" });
    stopPolling();
  }
};

const stopPolling = () => {
  if (pollTimer.value) {
    clearInterval(pollTimer.value);
    pollTimer.value = null;
  }
};

// Lifecycle
onMounted(() => {
  // Start polling immediately
  pollStatus();

  // Poll every 2 seconds
  pollTimer.value = setInterval(pollStatus, 2000);
});

onUnmounted(() => {
  stopPolling();
});
</script>

<style scoped>
.extraction-status {
  background: rgba(30, 30, 30, 0.8);
  border: 1px solid #333;
  border-radius: 8px;
  padding: 15px;
  margin: 15px 0;
}

.status-header {
  display: flex;
  align-items: flex-start;
  gap: 15px;
  margin-bottom: 15px;
  position: relative;
}

.status-indicator {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-weight: bold;
  font-size: 1.2rem;
}

.status-indicator.status-processing {
  background: rgba(59, 130, 246, 0.2);
  border: 2px solid #3b82f6;
}

.status-indicator.status-completed {
  background: rgba(74, 222, 128, 0.2);
  border: 2px solid #4ade80;
  color: #4ade80;
}

.status-indicator.status-failed {
  background: rgba(239, 68, 68, 0.2);
  border: 2px solid #ef4444;
  color: #ef4444;
}

.spinner {
  display: inline-block;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.status-text {
  flex: 1;
}

.status-label {
  margin: 0;
  font-weight: 600;
  color: #fff;
  font-size: 0.95rem;
}

.status-description {
  margin: 4px 0 0 0;
  color: #a0a0a0;
  font-size: 0.85rem;
}

.close-btn {
  position: absolute;
  right: 0;
  top: 0;
  background: none;
  border: none;
  color: #888;
  font-size: 1.5rem;
  cursor: pointer;
  padding: 0;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color 0.3s ease;
}

.close-btn:hover {
  color: #fff;
}

.progress-bar {
  height: 4px;
  background: #333;
  border-radius: 2px;
  overflow: hidden;
  margin-bottom: 15px;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #3b82f6, #60a5fa);
  animation: progress 1.5s ease-in-out infinite;
}

@keyframes progress {
  0% {
    width: 0%;
  }
  50% {
    width: 100%;
  }
  100% {
    width: 0%;
  }
}

.results-summary {
  border-top: 1px solid #444;
  padding-top: 15px;
}

.summary-items {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 15px;
}

.summary-item {
  display: flex;
  align-items: center;
  gap: 10px;
}

.item-icon {
  font-size: 1.5rem;
}

.item-label {
  margin: 0;
  color: #a0a0a0;
  font-size: 0.8rem;
}

.item-value {
  margin: 4px 0 0 0;
  color: #fff;
  font-weight: 600;
  font-size: 0.95rem;
}

.error-details {
  border-top: 1px solid #444;
  padding-top: 15px;
}

.error-text {
  margin: 0;
  color: #fca5a5;
  font-size: 0.9rem;
  line-height: 1.4;
}
</style>
