<template>
  <div class="step0-data-ingestion">
    <!-- Header -->
    <div class="step-header">
      <h2>📥 PHASE 0: Data Ingestion</h2>
      <p class="description">
        Extract real-world data from Twitter/X and financial news. Select
        profiles and market context for simulation.
      </p>
    </div>

    <!-- Tabs Navigation -->
    <div class="tabs-navigation">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        class="tab-btn"
        :class="{ active: activeTab === tab.id }"
        @click="activeTab = tab.id"
      >
        {{ tab.icon }} {{ tab.label }}
      </button>
    </div>

    <!-- Tab Content -->
    <div class="tab-content">
      <!-- Tab 1: Twitter Extraction -->
      <div v-if="activeTab === 'twitter'" class="tab-panel">
        <TwitterExtractForm
          @extract="handleTwitterExtract"
          :loading="twitterLoading"
        />

        <ExtractionStatus
          v-if="twitterExtractionId"
          :extraction-id="twitterExtractionId"
          :endpoint="`/api/graph/extract/twitter/${twitterExtractionId}`"
          @loaded="onTwitterLoaded"
        />

        <ProfilePreview
          v-if="twitterProfiles.length > 0"
          :profiles="twitterProfiles"
          :type="'twitter'"
        />
      </div>

      <!-- Tab 2: News Extraction -->
      <div v-if="activeTab === 'news'" class="tab-panel">
        <NewsExtractForm @extract="handleNewsExtract" :loading="newsLoading" />

        <ExtractionStatus
          v-if="newsExtractionId"
          :extraction-id="newsExtractionId"
          :endpoint="`/api/graph/extract/news/${newsExtractionId}`"
          @loaded="onNewsLoaded"
        />

        <ArticlePreview
          v-if="newsArticles.length > 0"
          :articles="newsArticles"
        />
      </div>

      <!-- Tab 3: Review & Select -->
      <div v-if="activeTab === 'review'" class="tab-panel">
        <div class="review-section">
          <h3>Selected Profiles ({{ selectedProfiles.length }})</h3>

          <div v-if="twitterProfiles.length > 0" class="profile-selection">
            <div
              v-for="profile in twitterProfiles"
              :key="profile.username"
              class="profile-card clickable"
              :class="{ selected: isProfileSelected(profile.username) }"
              @click="toggleProfileSelection(profile.username)"
            >
              <div class="profile-header">
                <span class="username">@{{ profile.username }}</span>
                <span
                  class="checkbox"
                  :class="{ checked: isProfileSelected(profile.username) }"
                  >✓</span
                >
              </div>
              <div class="profile-info">
                <p>
                  <strong>{{ profile.name }}</strong>
                </p>
                <p class="bio">{{ profile.bio }}</p>
                <p class="stats">
                  👥 {{ profile.followers_count }} followers | 📝
                  {{ profile.tweet_count }} tweets
                </p>
              </div>
            </div>
          </div>

          <div v-else class="empty-state">
            <p>
              No profiles extracted yet. Go to Twitter tab and extract some
              profiles.
            </p>
          </div>
        </div>

        <div class="review-section">
          <h3>Market Context ({{ selectedArticles.length }} articles)</h3>

          <div v-if="newsArticles.length > 0" class="articles-selection">
            <div
              v-for="article in newsArticles"
              :key="article.url"
              class="article-card clickable"
              :class="{ selected: isArticleSelected(article.url) }"
              @click="toggleArticleSelection(article.url)"
            >
              <div class="article-header">
                <h4>{{ article.title }}</h4>
                <span
                  class="checkbox"
                  :class="{ checked: isArticleSelected(article.url) }"
                  >✓</span
                >
              </div>
              <p class="source">
                {{ article.source }} • {{ formatDate(article.published_at) }}
              </p>
              <p class="summary">{{ article.summary }}</p>
              <div class="tags">
                <span
                  v-for="asset in article.mentioned_assets"
                  :key="asset"
                  class="tag"
                >
                  {{ asset }}
                </span>
              </div>
            </div>
          </div>

          <div v-else class="empty-state">
            <p>
              No articles extracted yet. Go to News tab and extract some
              articles.
            </p>
          </div>
        </div>

        <!-- Action Buttons -->
        <div class="action-buttons">
          <button class="btn btn-secondary" @click="activeTab = 'twitter'">
            ← Back to Extract
          </button>

          <button
            class="btn btn-primary"
            :disabled="selectedProfiles.length === 0"
            @click="proceedToGraphBuild"
          >
            Proceed to Graph Build →
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from "vue";
import TwitterExtractForm from "./TwitterExtractForm.vue";
import NewsExtractForm from "./NewsExtractForm.vue";
import ExtractionStatus from "./ExtractionStatus.vue";
import ProfilePreview from "./ProfilePreview.vue";
import ArticlePreview from "./ArticlePreview.vue";
import { extractTwitter, extractNews } from "../api/dataIngestion.js";

// State
const activeTab = ref("twitter");

const tabs = [
  { id: "twitter", label: "Twitter/X", icon: "𝕏" },
  { id: "news", label: "News", icon: "📰" },
  { id: "review", label: "Review & Select", icon: "✓" },
];

// Twitter Extraction
const twitterExtractionId = ref(null);
const twitterProfiles = ref([]);
const twitterLoading = ref(false);

// News Extraction
const newsExtractionId = ref(null);
const newsArticles = ref([]);
const newsLoading = ref(false);

// Selection
const selectedProfileUsernames = ref(new Set());
const selectedArticleUrls = ref(new Set());

// Computed
const selectedProfiles = computed(() =>
  twitterProfiles.value.filter((p) =>
    selectedProfileUsernames.value.has(p.username),
  ),
);

const selectedArticles = computed(() =>
  newsArticles.value.filter((a) => selectedArticleUrls.value.has(a.url)),
);

// Emits
const emit = defineEmits(["next-step", "data-selected"]);

// Methods
const handleTwitterExtract = async (params) => {
  twitterLoading.value = true;
  try {
    const result = await extractTwitter(params);
    twitterExtractionId.value = result.extraction_id;
  } catch (error) {
    console.error("Twitter extraction error:", error);
  } finally {
    twitterLoading.value = false;
  }
};

const handleNewsExtract = async (params) => {
  newsLoading.value = true;
  try {
    const result = await extractNews(params);
    newsExtractionId.value = result.extraction_id;
  } catch (error) {
    console.error("News extraction error:", error);
  } finally {
    newsLoading.value = false;
  }
};

const onTwitterLoaded = (data) => {
  twitterProfiles.value = data.profiles || [];
};

const onNewsLoaded = (data) => {
  newsArticles.value = data.articles || [];
};

const isProfileSelected = (username) =>
  selectedProfileUsernames.value.has(username);

const toggleProfileSelection = (username) => {
  if (selectedProfileUsernames.value.has(username)) {
    selectedProfileUsernames.value.delete(username);
  } else {
    selectedProfileUsernames.value.add(username);
  }
};

const isArticleSelected = (url) => selectedArticleUrls.value.has(url);

const toggleArticleSelection = (url) => {
  if (selectedArticleUrls.value.has(url)) {
    selectedArticleUrls.value.delete(url);
  } else {
    selectedArticleUrls.value.add(url);
  }
};

const formatDate = (dateString) => {
  return new Date(dateString).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
};

const proceedToGraphBuild = () => {
  const simulationData = {
    profiles: selectedProfiles.value,
    articles: selectedArticles.value,
    extractedAt: new Date().toISOString(),
  };

  emit("data-selected", simulationData);
  emit("next-step");
};
</script>

<style scoped>
.step0-data-ingestion {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: linear-gradient(135deg, #1a1a1a 0%, #0f0f0f 100%);
  color: #e0e0e0;
  overflow: hidden;
}

.step-header {
  padding: 20px;
  border-bottom: 1px solid #333;
  background: rgba(20, 20, 20, 0.9);
}

.step-header h2 {
  margin: 0 0 8px 0;
  font-size: 1.5rem;
  color: #fff;
}

.description {
  margin: 0;
  font-size: 0.9rem;
  color: #a0a0a0;
}

.tabs-navigation {
  display: flex;
  border-bottom: 1px solid #333;
  background: rgba(20, 20, 20, 0.9);
  padding: 0 20px;
}

.tab-btn {
  flex: 1;
  padding: 15px 20px;
  border: none;
  background: transparent;
  color: #a0a0a0;
  cursor: pointer;
  font-size: 0.95rem;
  transition: all 0.3s ease;
  border-bottom: 2px solid transparent;
}

.tab-btn:hover {
  color: #fff;
  background: rgba(255, 255, 255, 0.05);
}

.tab-btn.active {
  color: #4ade80;
  border-bottom-color: #4ade80;
}

.tab-content {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.tab-panel {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.review-section {
  background: rgba(30, 30, 30, 0.8);
  border: 1px solid #333;
  border-radius: 8px;
  padding: 20px;
}

.review-section h3 {
  margin: 0 0 15px 0;
  font-size: 1.1rem;
  color: #fff;
}

.profile-selection,
.articles-selection {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 15px;
}

.profile-card,
.article-card {
  background: rgba(40, 40, 40, 0.8);
  border: 1px solid #444;
  border-radius: 8px;
  padding: 15px;
  transition: all 0.3s ease;
  cursor: pointer;
}

.profile-card:hover,
.article-card:hover {
  background: rgba(50, 50, 50, 0.8);
  border-color: #555;
}

.profile-card.selected,
.article-card.selected {
  background: rgba(74, 222, 128, 0.1);
  border-color: #4ade80;
}

.profile-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.username {
  font-weight: bold;
  color: #4ade80;
}

.checkbox {
  width: 20px;
  height: 20px;
  border: 2px solid #666;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: transparent;
  transition: all 0.3s ease;
}

.checkbox.checked {
  background: #4ade80;
  border-color: #4ade80;
  color: #000;
}

.profile-info p {
  margin: 5px 0;
  font-size: 0.85rem;
}

.bio {
  color: #a0a0a0;
  line-height: 1.4;
  max-height: 60px;
  overflow: hidden;
}

.stats {
  color: #888;
  font-size: 0.8rem;
}

.article-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 8px;
}

.article-header h4 {
  margin: 0;
  font-size: 0.95rem;
  color: #fff;
  flex: 1;
}

.source {
  color: #888;
  font-size: 0.8rem;
  margin: 5px 0;
}

.summary {
  color: #a0a0a0;
  font-size: 0.85rem;
  line-height: 1.4;
  max-height: 80px;
  overflow: hidden;
}

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: 10px;
}

.tag {
  background: rgba(74, 222, 128, 0.15);
  color: #4ade80;
  padding: 3px 8px;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: bold;
}

.empty-state {
  text-align: center;
  padding: 40px 20px;
  color: #888;
}

.action-buttons {
  display: flex;
  gap: 10px;
  margin-top: 20px;
  justify-content: flex-end;
}

.btn {
  padding: 10px 20px;
  border: none;
  border-radius: 6px;
  font-size: 0.95rem;
  cursor: pointer;
  transition: all 0.3s ease;
  font-weight: 500;
}

.btn-primary {
  background: #4ade80;
  color: #000;
}

.btn-primary:hover:not(:disabled) {
  background: #22c55e;
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-secondary {
  background: transparent;
  border: 1px solid #666;
  color: #e0e0e0;
}

.btn-secondary:hover {
  background: rgba(255, 255, 255, 0.1);
}
</style>
