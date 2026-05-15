/**
 * Data Ingestion API Service
 * Handles Twitter and News extraction requests
 */

import axios from 'axios'

const API_BASE = '/api/graph'

// ============= Twitter Extraction =============

export async function extractTwitter(params) {
  /**
   * Start Twitter/X profile extraction
   * 
   * @param {Object} params
   * @param {string} params.query - Username or search query
   * @param {string} params.extract_type - 'profile' or 'search'
   * @param {number} params.limit - Max results (1-50)
   * @param {boolean} params.include_tweets - Include recent tweets
   * 
   * @returns {Object} { success, extraction_id, status }
   */
  const response = await axios.post(`${API_BASE}/extract/twitter`, {
    query: params.query,
    extract_type: params.extractType || 'profile',
    limit: params.limit || 10,
    include_tweets: params.includeTweets !== false
  })
  
  return response.data
}

export async function getTwitterExtractionStatus(extractionId) {
  /**
   * Get Twitter extraction status and results
   * 
   * @param {string} extractionId - Extraction session ID
   * 
   * @returns {Object} { success, status, profiles, tweets, error }
   */
  const response = await axios.get(`${API_BASE}/extract/twitter/${extractionId}`)
  return response.data
}

// Poll for extraction status with auto-retry
export async function pollTwitterExtraction(extractionId, maxAttempts = 60) {
  /**
   * Poll Twitter extraction until completed or failed
   * Polls every 2 seconds for up to 2 minutes
   * 
   * @param {string} extractionId
   * @param {number} maxAttempts - Max polling attempts
   * 
   * @returns {Object} Final extraction results
   */
  let attempts = 0
  
  while (attempts < maxAttempts) {
    const result = await getTwitterExtractionStatus(extractionId)
    
    if (result.status === 'completed' || result.status === 'failed') {
      return result
    }
    
    // Wait 2 seconds before next poll
    await new Promise(resolve => setTimeout(resolve, 2000))
    attempts++
  }
  
  throw new Error('Twitter extraction polling timeout')
}


// ============= News Extraction =============

export async function extractNews(params) {
  /**
   * Start financial news extraction
   * 
   * @param {Object} params
   * @param {string} params.query - Search query (ticker, keywords, etc)
   * @param {string[]} params.sources - News sources filter (optional)
   * @param {string} params.timeRange - '1d', '7d', or '30d'
   * @param {number} params.limit - Max articles (1-50)
   * 
   * @returns {Object} { success, extraction_id, status }
   */
  const response = await axios.post(`${API_BASE}/extract/news`, {
    query: params.query,
    sources: params.sources || null,
    time_range: params.timeRange || '7d',
    limit: params.limit || 10
  })
  
  return response.data
}

export async function getNewsExtractionStatus(extractionId) {
  /**
   * Get news extraction status and results
   * 
   * @param {string} extractionId - Extraction session ID
   * 
   * @returns {Object} { success, status, articles, error }
   */
  const response = await axios.get(`${API_BASE}/extract/news/${extractionId}`)
  return response.data
}

// Poll for extraction status with auto-retry
export async function pollNewsExtraction(extractionId, maxAttempts = 60) {
  /**
   * Poll news extraction until completed or failed
   * Polls every 2 seconds for up to 2 minutes
   * 
   * @param {string} extractionId
   * @param {number} maxAttempts - Max polling attempts
   * 
   * @returns {Object} Final extraction results
   */
  let attempts = 0
  
  while (attempts < maxAttempts) {
    const result = await getNewsExtractionStatus(extractionId)
    
    if (result.status === 'completed' || result.status === 'failed') {
      return result
    }
    
    // Wait 2 seconds before next poll
    await new Promise(resolve => setTimeout(resolve, 2000))
    attempts++
  }
  
  throw new Error('News extraction polling timeout')
}


// ============= Simulation Data Package =============

export async function prepareSimulationPackage(data) {
  /**
   * Create simulation data package from selected profiles and articles
   * 
   * @param {Object} data
   * @param {string[]} data.selectedProfileIds - Selected profile usernames
   * @param {string[]} data.selectedArticleIds - Selected article URLs
   * @param {Object} data.simulationConfig - Simulation parameters
   * 
   * @returns {Object} { success, package_id, profiles, articles }
   */
  const response = await axios.post(`${API_BASE}/prepare-simulation-package`, {
    selected_profile_ids: data.selectedProfileIds || [],
    selected_article_ids: data.selectedArticleIds || [],
    simulation_config: data.simulationConfig || {}
  })
  
  return response.data
}

export async function clearExtractions() {
  /**
   * Clear all cached extractions (for testing/cleanup)
   * 
   * @returns {Object} { success, cleared }
   */
  const response = await axios.post(`${API_BASE}/clear-extractions`)
  return response.data
}
