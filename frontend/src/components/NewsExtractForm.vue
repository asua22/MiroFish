<template>
  <div class="news-extract-form">
    <div class="form-header">
      <h3>📰 Extract Financial News</h3>
      <p>Search for market news, earnings reports, and economic events</p>
    </div>

    <form @submit.prevent="handleSubmit" class="extract-form">
      <!-- Query Input -->
      <div class="form-group">
        <label for="news-query">Search Query</label>
        <input
          id="news-query"
          v-model="form.query"
          type="text"
          placeholder="e.g. Fed interest rates, AAPL earnings, bitcoin crash"
          class="form-input"
          :disabled="loading"
          required
        />
        <p class="help-text">
          Enter keywords, ticker symbols, or topics (e.g., TSLA, Fed, crypto,
          inflation)
        </p>
      </div>

      <!-- News Sources -->
      <div class="form-group">
        <label>News Sources</label>
        <div class="sources-grid">
          <label
            v-for="source in availableSources"
            :key="source"
            class="source-checkbox"
          >
            <input
              v-model="form.sources"
              type="checkbox"
              :value="source"
              :disabled="loading"
            />
            <span>{{ source }}</span>
          </label>
        </div>
        <p class="help-text">
          Select sources or leave empty to search all. (Reuters, Bloomberg,
          CNBC, etc.)
        </p>
      </div>

      <!-- Time Range -->
      <div class="form-group">
        <label for="time-range">Time Range</label>
        <select
          id="time-range"
          v-model="form.timeRange"
          class="form-select"
          :disabled="loading"
        >
          <option value="1d">Last 24 Hours</option>
          <option value="7d">Last 7 Days</option>
          <option value="30d">Last 30 Days</option>
        </select>
        <p class="help-text">Articles published within this period</p>
      </div>

      <!-- Limit -->
      <div class="form-group">
        <label for="news-limit">Max Articles</label>
        <div class="input-with-slider">
          <input
            id="news-limit"
            v-model.number="form.limit"
            type="range"
            min="1"
            max="50"
            class="form-slider"
            :disabled="loading"
          />
          <span class="limit-display">{{ form.limit }}</span>
        </div>
        <p class="help-text">Maximum number of articles to extract (1-50)</p>
      </div>

      <!-- Submit Button -->
      <div class="form-actions">
        <button
          type="submit"
          class="btn btn-primary"
          :disabled="loading || !form.query"
        >
          <span v-if="!loading">🔍 Search News</span>
          <span v-else>⏳ Searching...</span>
        </button>
        <span v-if="loading" class="loading-spinner"></span>
      </div>
    </form>

    <!-- Error Message -->
    <div v-if="error" class="error-message">
      <span class="error-icon">⚠️</span>
      <div>
        <p><strong>Search Error</strong></p>
        <p>{{ error }}</p>
      </div>
    </div>

    <!-- Info Box -->
    <div class="info-box">
      <p>
        <strong>💡 Tip:</strong> Search for specific tickers (TSLA, AAPL, BTC)
        or broader topics (Fed, crypto, earnings). News extraction takes 30-90
        seconds depending on results available.
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue";

// Available sources
const availableSources = [
  "Reuters",
  "Bloomberg",
  "CNBC",
  "MarketWatch",
  "Yahoo Finance",
  "Financial Times",
  "Seeking Alpha",
];

// Form state
const form = ref({
  query: "",
  sources: [],
  timeRange: "7d",
  limit: 10,
});

const loading = ref(false);
const error = ref("");

// Emits
const emit = defineEmits(["extract"]);

// Methods
const handleSubmit = () => {
  // Reset error
  error.value = "";

  // Validate
  if (!form.value.query.trim()) {
    error.value = "Please enter a search query";
    return;
  }

  // Emit event
  loading.value = true;
  try {
    emit("extract", {
      query: form.value.query.trim(),
      sources: form.value.sources.length > 0 ? form.value.sources : undefined,
      timeRange: form.value.timeRange,
      limit: form.value.limit,
    });
  } catch (e) {
    error.value = e.message;
  } finally {
    loading.value = false;
  }
};
</script>

<style scoped>
.news-extract-form {
  background: rgba(30, 30, 30, 0.8);
  border: 1px solid #333;
  border-radius: 8px;
  padding: 20px;
}

.form-header {
  margin-bottom: 20px;
  border-bottom: 1px solid #444;
  padding-bottom: 15px;
}

.form-header h3 {
  margin: 0 0 8px 0;
  font-size: 1.2rem;
  color: #fff;
}

.form-header p {
  margin: 0;
  color: #a0a0a0;
  font-size: 0.9rem;
}

.extract-form {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-group label {
  color: #e0e0e0;
  font-weight: 500;
  font-size: 0.95rem;
}

.form-input,
.form-select {
  padding: 10px 12px;
  border: 1px solid #444;
  border-radius: 6px;
  background: rgba(50, 50, 50, 0.8);
  color: #e0e0e0;
  font-size: 0.95rem;
  transition: all 0.3s ease;
}

.form-input:focus,
.form-select:focus {
  outline: none;
  border-color: #60a5fa;
  background: rgba(50, 50, 50, 0.9);
  box-shadow: 0 0 8px rgba(96, 165, 250, 0.2);
}

.form-input:disabled,
.form-select:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.sources-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 10px;
}

.source-checkbox {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 8px 10px;
  border: 1px solid #444;
  border-radius: 6px;
  background: rgba(50, 50, 50, 0.8);
  transition: all 0.3s ease;
  color: #e0e0e0;
  font-size: 0.9rem;
}

.source-checkbox:hover {
  background: rgba(60, 60, 60, 0.8);
  border-color: #555;
}

.source-checkbox input[type="checkbox"] {
  width: 16px;
  height: 16px;
  cursor: pointer;
  accent-color: #60a5fa;
}

.source-checkbox input[type="checkbox"]:checked + span {
  color: #60a5fa;
  font-weight: 500;
}

.help-text {
  margin: 0;
  font-size: 0.8rem;
  color: #888;
  line-height: 1.4;
}

.input-with-slider {
  display: flex;
  align-items: center;
  gap: 15px;
}

.form-slider {
  flex: 1;
  height: 6px;
  border-radius: 3px;
  background: #444;
  outline: none;
  cursor: pointer;
  -webkit-appearance: none;
  appearance: none;
}

.form-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #60a5fa;
  cursor: pointer;
  transition: all 0.3s ease;
}

.form-slider::-moz-range-thumb {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #60a5fa;
  cursor: pointer;
  border: none;
  transition: all 0.3s ease;
}

.form-slider::-webkit-slider-thumb:hover {
  transform: scale(1.2);
  background: #3b82f6;
}

.limit-display {
  width: 40px;
  text-align: center;
  color: #60a5fa;
  font-weight: bold;
  font-size: 1rem;
}

.form-actions {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-top: 10px;
}

.btn {
  padding: 12px 24px;
  border: none;
  border-radius: 6px;
  font-size: 0.95rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.3s ease;
}

.btn-primary {
  background: #60a5fa;
  color: #000;
}

.btn-primary:hover:not(:disabled) {
  background: #3b82f6;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(96, 165, 250, 0.3);
}

.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.loading-spinner {
  width: 20px;
  height: 20px;
  border: 2px solid #444;
  border-top-color: #60a5fa;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.error-message {
  background: rgba(239, 68, 68, 0.15);
  border: 1px solid #dc2626;
  border-radius: 6px;
  padding: 12px;
  display: flex;
  gap: 12px;
  margin-top: 15px;
}

.error-icon {
  font-size: 1.2rem;
  flex-shrink: 0;
}

.error-message p {
  margin: 0;
  color: #fca5a5;
  font-size: 0.9rem;
  line-height: 1.4;
}

.error-message strong {
  color: #f87171;
}

.info-box {
  background: rgba(59, 130, 246, 0.1);
  border: 1px solid #3b82f6;
  border-radius: 6px;
  padding: 12px;
  margin-top: 15px;
}

.info-box p {
  margin: 0;
  color: #93c5fd;
  font-size: 0.9rem;
  line-height: 1.4;
}

.info-box strong {
  color: #60a5fa;
}
</style>
