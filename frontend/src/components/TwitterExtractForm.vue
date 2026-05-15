<template>
  <div class="twitter-extract-form">
    <div class="form-header">
      <h3>𝕏 Extract Twitter/X Data</h3>
      <p>Enter a username or search query to extract profiles and tweets</p>
    </div>

    <form @submit.prevent="handleSubmit" class="extract-form">
      <!-- Query Input -->
      <div class="form-group">
        <label for="query">Username or Search Query</label>
        <input
          id="query"
          v-model="form.query"
          type="text"
          placeholder="e.g. elonmusk or crypto traders"
          class="form-input"
          :disabled="loading"
          required
        />
        <p class="help-text">
          Enter a Twitter username (without @) or a search query
        </p>
      </div>

      <!-- Extract Type -->
      <div class="form-group">
        <label for="extract_type">Extract Type</label>
        <select
          id="extract_type"
          v-model="form.extractType"
          class="form-select"
          :disabled="loading"
        >
          <option value="profile">Single Profile</option>
          <option value="search">Search Results</option>
        </select>
        <p class="help-text">
          <strong>Profile:</strong> Extract detailed info from one user
          <strong>Search:</strong> Find multiple users matching query
        </p>
      </div>

      <!-- Limit -->
      <div class="form-group">
        <label for="limit">Max Results</label>
        <div class="input-with-slider">
          <input
            id="limit"
            v-model.number="form.limit"
            type="range"
            min="1"
            max="50"
            class="form-slider"
            :disabled="loading"
          />
          <span class="limit-display">{{ form.limit }}</span>
        </div>
        <p class="help-text">
          Maximum number of profiles/tweets to extract (1-50)
        </p>
      </div>

      <!-- Include Tweets -->
      <div class="form-group checkbox-group">
        <label for="include_tweets" class="checkbox-label">
          <input
            id="include_tweets"
            v-model="form.includeTweets"
            type="checkbox"
            :disabled="loading"
          />
          <span>Include Recent Tweets</span>
        </label>
        <p class="help-text">
          Extract recent tweets from the profile(s) for sentiment analysis
        </p>
      </div>

      <!-- Submit Button -->
      <div class="form-actions">
        <button
          type="submit"
          class="btn btn-primary"
          :disabled="loading || !form.query"
        >
          <span v-if="!loading">🔍 Extract Data</span>
          <span v-else>⏳ Extracting...</span>
        </button>
        <span v-if="loading" class="loading-spinner"></span>
      </div>
    </form>

    <!-- Error Message -->
    <div v-if="error" class="error-message">
      <span class="error-icon">⚠️</span>
      <div>
        <p><strong>Extraction Error</strong></p>
        <p>{{ error }}</p>
      </div>
    </div>

    <!-- Info Box -->
    <div class="info-box">
      <p>
        <strong>💡 Tip:</strong> For best results, use existing Twitter handles
        or specific keywords related to finance/markets. Extraction typically
        takes 30-60 seconds.
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue";

// Form state
const form = ref({
  query: "",
  extractType: "profile",
  limit: 10,
  includeTweets: true,
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
    error.value = "Please enter a username or search query";
    return;
  }

  // Emit event
  loading.value = true;
  try {
    emit("extract", {
      query: form.value.query.trim(),
      extractType: form.value.extractType,
      limit: form.value.limit,
      includeTweets: form.value.includeTweets,
    });
  } catch (e) {
    error.value = e.message;
  } finally {
    loading.value = false;
  }
};
</script>

<style scoped>
.twitter-extract-form {
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
  border-color: #4ade80;
  background: rgba(50, 50, 50, 0.9);
  box-shadow: 0 0 8px rgba(74, 222, 128, 0.2);
}

.form-input:disabled,
.form-select:disabled {
  opacity: 0.6;
  cursor: not-allowed;
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
  background: #4ade80;
  cursor: pointer;
  transition: all 0.3s ease;
}

.form-slider::-moz-range-thumb {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #4ade80;
  cursor: pointer;
  border: none;
  transition: all 0.3s ease;
}

.form-slider::-webkit-slider-thumb:hover {
  transform: scale(1.2);
  background: #22c55e;
}

.limit-display {
  width: 40px;
  text-align: center;
  color: #4ade80;
  font-weight: bold;
  font-size: 1rem;
}

.checkbox-group {
  flex-direction: row;
  align-items: flex-start;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  color: #e0e0e0;
  font-weight: 500;
}

.checkbox-label input[type="checkbox"] {
  width: 18px;
  height: 18px;
  cursor: pointer;
  accent-color: #4ade80;
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
  background: #4ade80;
  color: #000;
}

.btn-primary:hover:not(:disabled) {
  background: #22c55e;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(74, 222, 128, 0.3);
}

.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.loading-spinner {
  width: 20px;
  height: 20px;
  border: 2px solid #444;
  border-top-color: #4ade80;
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
