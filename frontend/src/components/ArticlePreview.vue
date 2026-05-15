<template>
  <div class="article-preview">
    <div class="preview-header">
      <h3>📰 News Articles</h3>
      <span class="count">{{ articles.length }} articles</span>
    </div>

    <div class="articles-list">
      <div v-for="article in articles" :key="article.url" class="article-item">
        <!-- Header -->
        <div class="article-header">
          <h4 class="title">{{ article.title }}</h4>
          <span class="sentiment" :class="`sentiment-${article.sentiment}`">
            {{ sentimentIcon(article.sentiment) }}
            {{ article.sentiment || "N/A" }}
          </span>
        </div>

        <!-- Meta Info -->
        <div class="meta-info">
          <span class="source">{{ article.source }}</span>
          <span class="divider">•</span>
          <span class="date">{{ formatDate(article.published_at) }}</span>
          <span v-if="article.impact_level" class="divider">•</span>
          <span
            v-if="article.impact_level"
            class="impact"
            :class="`impact-${article.impact_level}`"
          >
            {{ article.impact_level }} Impact
          </span>
        </div>

        <!-- Summary -->
        <p class="summary">{{ article.summary }}</p>

        <!-- Mentioned Assets -->
        <div
          v-if="article.mentioned_assets && article.mentioned_assets.length > 0"
          class="assets"
        >
          <span class="assets-label">Mentions:</span>
          <div class="assets-list">
            <span
              v-for="asset in article.mentioned_assets"
              :key="asset"
              class="asset-tag"
            >
              {{ asset }}
            </span>
          </div>
        </div>

        <!-- Topics -->
        <div v-if="article.topics && article.topics.length > 0" class="topics">
          <span
            v-for="topic in article.topics.slice(0, 5)"
            :key="topic"
            class="topic-tag"
          >
            {{ topic }}
          </span>
        </div>

        <!-- Read Link -->
        <a
          :href="article.url"
          target="_blank"
          rel="noopener noreferrer"
          class="read-link"
        >
          Read full article →
        </a>
      </div>
    </div>
  </div>
</template>

<script setup>
import { defineProps } from "vue";

defineProps({
  articles: {
    type: Array,
    required: true,
  },
});

// Methods
const formatDate = (dateString) => {
  return new Date(dateString).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
};

const sentimentIcon = (sentiment) => {
  const icons = {
    positive: "📈",
    negative: "📉",
    neutral: "➖",
  };
  return icons[sentiment] || "❓";
};
</script>

<style scoped>
.article-preview {
  background: rgba(30, 30, 30, 0.8);
  border: 1px solid #333;
  border-radius: 8px;
  padding: 20px;
  margin: 15px 0;
}

.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
  padding-bottom: 15px;
  border-bottom: 1px solid #444;
}

.preview-header h3 {
  margin: 0;
  font-size: 1.1rem;
  color: #fff;
}

.count {
  background: rgba(96, 165, 250, 0.15);
  color: #60a5fa;
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 0.8rem;
  font-weight: 600;
}

.articles-list {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.article-item {
  background: rgba(40, 40, 40, 0.8);
  border: 1px solid #444;
  border-radius: 8px;
  padding: 15px;
  transition: all 0.3s ease;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.article-item:hover {
  background: rgba(50, 50, 50, 0.8);
  border-color: #60a5fa;
  transform: translateX(4px);
}

.article-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 10px;
}

.title {
  margin: 0;
  color: #fff;
  font-size: 0.95rem;
  line-height: 1.4;
  flex: 1;
}

.sentiment {
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 600;
  white-space: nowrap;
  flex-shrink: 0;
}

.sentiment-positive {
  background: rgba(74, 222, 128, 0.15);
  color: #4ade80;
}

.sentiment-negative {
  background: rgba(239, 68, 68, 0.15);
  color: #fca5a5;
}

.sentiment-neutral {
  background: rgba(107, 114, 128, 0.15);
  color: #d1d5db;
}

.meta-info {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}

.source {
  color: #60a5fa;
  font-weight: 600;
  font-size: 0.85rem;
}

.date {
  color: #888;
  font-size: 0.85rem;
}

.divider {
  color: #555;
}

.impact {
  font-size: 0.8rem;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 3px;
}

.impact-high {
  background: rgba(239, 68, 68, 0.15);
  color: #fca5a5;
}

.impact-medium {
  background: rgba(245, 158, 11, 0.15);
  color: #fbbf24;
}

.impact-low {
  background: rgba(74, 222, 128, 0.15);
  color: #4ade80;
}

.summary {
  margin: 0;
  color: #a0a0a0;
  font-size: 0.9rem;
  line-height: 1.5;
  max-height: 80px;
  overflow: hidden;
}

.assets {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.assets-label {
  color: #888;
  font-size: 0.8rem;
  font-weight: 600;
}

.assets-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.asset-tag {
  background: rgba(251, 146, 60, 0.15);
  color: #fb923c;
  padding: 3px 8px;
  border-radius: 3px;
  font-size: 0.75rem;
  font-weight: 600;
}

.topics {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.topic-tag {
  background: rgba(139, 92, 246, 0.15);
  color: #d8b4fe;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 0.75rem;
}

.read-link {
  color: #60a5fa;
  text-decoration: none;
  font-size: 0.85rem;
  margin-top: 8px;
  transition: all 0.3s ease;
  font-weight: 500;
  width: fit-content;
}

.read-link:hover {
  color: #3b82f6;
}
</style>
