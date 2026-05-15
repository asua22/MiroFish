<template>
  <div class="profile-preview">
    <div class="preview-header">
      <h3>{{ type === "twitter" ? "𝕏 Twitter Profiles" : "Profiles" }}</h3>
      <span class="count">{{ profiles.length }} profiles</span>
    </div>

    <div class="profiles-grid">
      <div
        v-for="profile in profiles"
        :key="profile.username"
        class="profile-card"
      >
        <!-- Avatar -->
        <div class="profile-avatar">
          <img
            v-if="profile.avatar_url"
            :src="profile.avatar_url"
            :alt="profile.username"
            class="avatar-image"
          />
          <div v-else class="avatar-placeholder">
            {{ profile.name.charAt(0).toUpperCase() }}
          </div>
          <span v-if="profile.verified" class="verified-badge">✓</span>
        </div>

        <!-- Info -->
        <div class="profile-info">
          <h4 class="username">@{{ profile.username }}</h4>
          <p class="name">{{ profile.name }}</p>

          <p class="bio">{{ truncate(profile.bio, 100) }}</p>

          <!-- Stats -->
          <div class="stats">
            <div class="stat">
              <span class="stat-value">{{
                formatNumber(profile.followers_count)
              }}</span>
              <span class="stat-label">Followers</span>
            </div>
            <div class="stat">
              <span class="stat-value">{{
                formatNumber(profile.tweet_count)
              }}</span>
              <span class="stat-label">Tweets</span>
            </div>
          </div>

          <!-- Tags -->
          <div v-if="profile.location || profile.website" class="tags">
            <span v-if="profile.location" class="tag"
              >📍 {{ profile.location }}</span
            >
            <span v-if="profile.website" class="tag">🔗 Website</span>
          </div>

          <!-- Action Link -->
          <a
            :href="`https://x.com/${profile.username}`"
            target="_blank"
            rel="noopener noreferrer"
            class="profile-link"
          >
            View on X →
          </a>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { defineProps } from "vue";

defineProps({
  profiles: {
    type: Array,
    required: true,
  },
  type: {
    type: String,
    default: "twitter",
  },
});

// Methods
const truncate = (text, length) => {
  if (!text) return "";
  return text.length > length ? text.substring(0, length) + "..." : text;
};

const formatNumber = (num) => {
  if (!num) return "0";
  if (num >= 1000000) return (num / 1000000).toFixed(1) + "M";
  if (num >= 1000) return (num / 1000).toFixed(1) + "K";
  return num.toString();
};
</script>

<style scoped>
.profile-preview {
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
  background: rgba(74, 222, 128, 0.15);
  color: #4ade80;
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 0.8rem;
  font-weight: 600;
}

.profiles-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 15px;
}

.profile-card {
  background: rgba(40, 40, 40, 0.8);
  border: 1px solid #444;
  border-radius: 8px;
  padding: 15px;
  transition: all 0.3s ease;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.profile-card:hover {
  background: rgba(50, 50, 50, 0.8);
  border-color: #4ade80;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(74, 222, 128, 0.1);
}

.profile-avatar {
  position: relative;
  width: 60px;
  height: 60px;
  border-radius: 50%;
  overflow: hidden;
  background: linear-gradient(135deg, #4ade80, #22c55e);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  font-size: 1.5rem;
  color: #000;
}

.avatar-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.avatar-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.verified-badge {
  position: absolute;
  bottom: 0;
  right: 0;
  width: 20px;
  height: 20px;
  background: #4ade80;
  color: #000;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.75rem;
  font-weight: bold;
}

.profile-info {
  flex: 1;
}

.username {
  margin: 0;
  color: #4ade80;
  font-size: 0.9rem;
  font-weight: 600;
}

.name {
  margin: 4px 0 0 0;
  color: #fff;
  font-size: 0.95rem;
  font-weight: 500;
}

.bio {
  margin: 6px 0 0 0;
  color: #a0a0a0;
  font-size: 0.85rem;
  line-height: 1.4;
}

.stats {
  display: flex;
  gap: 15px;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid #555;
}

.stat {
  display: flex;
  flex-direction: column;
}

.stat-value {
  color: #4ade80;
  font-weight: 600;
  font-size: 0.9rem;
}

.stat-label {
  color: #888;
  font-size: 0.75rem;
  margin-top: 2px;
}

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
}

.tag {
  background: rgba(59, 130, 246, 0.1);
  color: #93c5fd;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 0.75rem;
}

.profile-link {
  color: #4ade80;
  text-decoration: none;
  font-size: 0.85rem;
  margin-top: 8px;
  transition: all 0.3s ease;
  font-weight: 500;
}

.profile-link:hover {
  color: #22c55e;
}
</style>
