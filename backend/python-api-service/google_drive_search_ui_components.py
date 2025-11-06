"""
Google Drive Search UI Components
React/Vue components for Google Drive search integration
"""

import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

@dataclass
class UIComponent:
    """UI Component model"""
    name: str
    type: str
    props: Dict[str, Any]
    styles: Dict[str, Any]
    events: List[str]

class GoogleDriveSearchComponents:
    """Google Drive Search UI Components"""
    
    def __init__(self):
        self.components = {}
        self._initialize_components()
    
    def _initialize_components(self):
        """Initialize all Google Drive search UI components"""
        
        # Search Bar Component
        self.components["search_bar"] = UIComponent(
            name="GoogleDriveSearchBar",
            type="search_input",
            props={
                "placeholder": "Search your Google Drive files...",
                "provider": "google_drive",
                "show_voice_search": True,
                "show_advanced_search": True,
                "auto_suggestions": True,
                "suggestion_types": ["history", "popular", "semantic"],
                "debounce_time": 300,
                "min_search_length": 1
            },
            styles={
                "width": "100%",
                "height": "48px",
                "border_radius": "8px",
                "background": "#ffffff",
                "border": "1px solid #e0e0e0",
                "font_size": "16px"
            },
            events=["onSearch", "onFocus", "onBlur", "onSuggestionSelect"]
        )
        
        # Advanced Search Component
        self.components["advanced_search"] = UIComponent(
            name="GoogleDriveAdvancedSearch",
            type="advanced_search",
            props={
                "fields": [
                    {
                        "name": "query",
                        "label": "Search Query",
                        "type": "text",
                        "placeholder": "Enter search terms...",
                        "required": True
                    },
                    {
                        "name": "file_type",
                        "label": "File Type",
                        "type": "select",
                        "multiple": True,
                        "options": [
                            {"value": "document", "label": "Documents"},
                            {"value": "image", "label": "Images"},
                            {"value": "video", "label": "Videos"},
                            {"value": "audio", "label": "Audio"},
                            {"value": "folder", "label": "Folders"},
                            {"value": "archive", "label": "Archives"}
                        ]
                    },
                    {
                        "name": "size_range",
                        "label": "File Size",
                        "type": "range",
                        "min": 0,
                        "max": 10737418240,  # 10GB
                        "unit": "bytes",
                        "presets": [
                            {"label": "Small (< 1MB)", "min": 0, "max": 1048576},
                            {"label": "Medium (1-10MB)", "min": 1048576, "max": 10485760},
                            {"label": "Large (10-100MB)", "min": 10485760, "max": 104857600},
                            {"label": "Extra Large (> 100MB)", "min": 104857600, "max": 10737418240}
                        ]
                    },
                    {
                        "name": "date_range",
                        "label": "Date Modified",
                        "type": "date_range",
                        "presets": [
                            {"label": "Today", "type": "relative", "value": "today"},
                            {"label": "Yesterday", "type": "relative", "value": "yesterday"},
                            {"label": "This Week", "type": "relative", "value": "week"},
                            {"label": "This Month", "type": "relative", "value": "month"},
                            {"label": "This Year", "type": "relative", "value": "year"}
                        ]
                    },
                    {
                        "name": "owner",
                        "label": "Owner",
                        "type": "select",
                        "multiple": True,
                        "async": True,
                        "api_endpoint": "/api/google-drive/users"
                    },
                    {
                        "name": "shared",
                        "label": "Shared Status",
                        "type": "checkbox",
                        "options": [
                            {"value": "shared", "label": "Shared with me"},
                            {"value": "not_shared", "label": "Not shared"}
                        ]
                    },
                    {
                        "name": "folder_path",
                        "label": "Folder Path",
                        "type": "folder_selector",
                        "api_endpoint": "/api/google-drive/folders",
                        "show_breadcrumbs": True
                    }
                ],
                "search_types": [
                    {"value": "semantic", "label": "AI-Powered Semantic Search", "description": "Find files based on meaning and context"},
                    {"value": "text", "label": "Full-Text Search", "description": "Search within file content"},
                    {"value": "metadata", "label": "Metadata Search", "description": "Search file names and properties"},
                    {"value": "visual", "label": "Visual Search", "description": "Search images visually"},
                    {"value": "advanced", "label": "Advanced Query", "description": "Use complex search syntax"}
                ],
                "sort_options": [
                    {"value": "relevance", "label": "Relevance"},
                    {"value": "date_modified", "label": "Date Modified"},
                    {"value": "date_created", "label": "Date Created"},
                    {"value": "name", "label": "Name"},
                    {"value": "size", "label": "Size"},
                    {"value": "owner", "label": "Owner"}
                ],
                "save_search": True,
                "load_saved_searches": True
            },
            styles={
                "background": "#f8f9fa",
                "padding": "20px",
                "border_radius": "12px",
                "border": "1px solid #e9ecef"
            },
            events=["onSearch", "onSaveSearch", "onLoadSavedSearch"]
        )
        
        # Search Filters Component
        self.components["search_filters"] = UIComponent(
            name="GoogleDriveSearchFilters",
            type="filter_panel",
            props={
                "collapsible": True,
                "persist_filters": True,
                "filter_categories": [
                    {
                        "name": "file_type",
                        "label": "File Type",
                        "type": "checkbox_group",
                        "options": [
                            {"value": "document", "label": "📄 Documents", "count": 0},
                            {"value": "image", "label": "🖼️ Images", "count": 0},
                            {"value": "video", "label": "🎬 Videos", "count": 0},
                            {"value": "audio", "label": "🎵 Audio", "count": 0},
                            {"value": "folder", "label": "📁 Folders", "count": 0},
                            {"value": "archive", "label": "📦 Archives", "count": 0}
                        ],
                        "collapsible": True
                    },
                    {
                        "name": "size",
                        "label": "File Size",
                        "type": "range_slider",
                        "min": 0,
                        "max": 10737418240,
                        "step": 1048576,
                        "format": "size",
                        "collapsible": True
                    },
                    {
                        "name": "date_modified",
                        "label": "Modified Date",
                        "type": "date_histogram",
                        "collapsible": True
                    },
                    {
                        "name": "owner",
                        "label": "Owner",
                        "type": "multi_select",
                        "async": True,
                        "api_endpoint": "/api/google-drive/users",
                        "collapsible": True
                    },
                    {
                        "name": "shared",
                        "label": "Shared Status",
                        "type": "radio_group",
                        "options": [
                            {"value": "all", "label": "All Files"},
                            {"value": "shared", "label": "🔗 Shared"},
                            {"value": "not_shared", "label": "🔒 Not Shared"}
                        ],
                        "collapsible": False
                    },
                    {
                        "name": "folder",
                        "label": "Folder",
                        "type": "folder_tree",
                        "api_endpoint": "/api/google-drive/folders",
                        "collapsible": True
                    },
                    {
                        "name": "tags",
                        "label": "Tags",
                        "type": "tag_selector",
                        "async": True,
                        "api_endpoint": "/api/google-drive/tags",
                        "collapsible": True
                    }
                ]
            },
            styles={
                "width": "280px",
                "background": "#ffffff",
                "border": "1px solid #e0e0e0",
                "border_radius": "8px",
                "padding": "16px"
            },
            events=["onFilterChange", "onFilterReset", "onFilterSave"]
        )
        
        # Search Results Component
        self.components["search_results"] = UIComponent(
            name="GoogleDriveSearchResults",
            type="results_container",
            props={
                "view_types": [
                    {"value": "list", "label": "📋 List", "icon": "list"},
                    {"value": "grid", "label": "⊞ Grid", "icon": "grid"},
                    {"value": "thumbnail", "label": "🖼️ Thumbnails", "icon": "image"},
                    {"value": "detail", "label": "📄 Details", "icon": "info"},
                    {"value": "timeline", "label": "📅 Timeline", "icon": "calendar"},
                    {"value": "tree", "label": "🌳 Tree", "icon": "folder-tree"}
                ],
                "default_view": "list",
                "columns": [
                    {
                        "key": "name",
                        "label": "Name",
                        "width": "40%",
                        "sortable": True,
                        "resizable": True,
                        "component": "FileLink"
                    },
                    {
                        "key": "modified_time",
                        "label": "Modified",
                        "width": "15%",
                        "sortable": True,
                        "component": "FormattedDate"
                    },
                    {
                        "key": "size",
                        "label": "Size",
                        "width": "10%",
                        "sortable": True,
                        "component": "FormattedSize"
                    },
                    {
                        "key": "owners",
                        "label": "Owner",
                        "width": "15%",
                        "sortable": True,
                        "component": "OwnerChips"
                    },
                    {
                        "key": "actions",
                        "label": "Actions",
                        "width": "20%",
                        "component": "ActionButtons",
                        "fixed": True
                    }
                ],
                "item_component": "GoogleDriveFileItem",
                "pagination": {
                    "enabled": True,
                    "page_size": 50,
                    "page_size_options": [25, 50, 100, 200],
                    "show_total": True,
                    "show_jump_to_page": True
                },
                "selection": {
                    "enabled": True,
                    "type": "checkbox",
                    "show_select_all": True,
                    "bulk_actions": [
                        {"action": "download", "label": "⬇️ Download"},
                        {"action": "move", "label": "📁 Move"},
                        {"action": "copy", "label": "📋 Copy"},
                        {"action": "share", "label": "🔗 Share"},
                        {"action": "delete", "label": "🗑️ Delete"},
                        {"action": "add_to_workflow", "label": "🤖 Add to Workflow"}
                    ]
                },
                "sorting": {
                    "enabled": True,
                    "default_sort": "relevance",
                    "multi_sort": True
                },
                "grouping": {
                    "enabled": True,
                    "default_group": None,
                    "group_options": [
                        {"value": "date_modified", "label": "Date Modified"},
                        {"value": "file_type", "label": "File Type"},
                        {"value": "owner", "label": "Owner"},
                        {"value": "folder", "label": "Folder"}
                    ]
                },
                "export": {
                    "enabled": True,
                    "formats": ["csv", "json", "xlsx"],
                    "include_metadata": True
                }
            },
            styles={
                "background": "#ffffff",
                "border_radius": "8px",
                "border": "1px solid #e0e0e0"
            },
            events=["onItemClick", "onItemSelect", "onBulkAction", "onSortChange", "onViewChange"]
        )
        
        # File Item Component
        self.components["file_item"] = UIComponent(
            name="GoogleDriveFileItem",
            type="list_item",
            props={
                "show_thumbnail": True,
                "show_file_icon": True,
                "show_file_info": True,
                "show_badges": True,
                "show_actions": True,
                "show_context_menu": True,
                "action_buttons": [
                    {"action": "download", "label": "⬇️", "tooltip": "Download"},
                    {"action": "view", "label": "👁️", "tooltip": "View"},
                    {"action": "share", "label": "🔗", "tooltip": "Share"},
                    {"action": "more", "label": "⋯", "tooltip": "More actions"}
                ],
                "context_menu": [
                    {"action": "open", "label": "Open", "icon": "folder-open"},
                    {"action": "download", "label": "Download", "icon": "download"},
                    {"action": "copy", "label": "Make a copy", "icon": "copy"},
                    {"action": "move", "label": "Move to", "icon": "folder"},
                    {"action": "rename", "label": "Rename", "icon": "edit"},
                    {"action": "share", "label": "Share", "icon": "share"},
                    {"action": "add_star", "label": "Add to Starred", "icon": "star"},
                    {"action": "details", "label": "View details", "icon": "info"},
                    {"action": "add_to_workflow", "label": "Add to Workflow", "icon": "robot"},
                    {"action": "delete", "label": "Delete", "icon": "trash", "danger": True}
                ]
            },
            styles={
                "padding": "12px 16px",
                "border_bottom": "1px solid #f0f0f0",
                "hover_background": "#f8f9fa"
            },
            events=["onClick", "onAction", "onSelect", "onContextMenu"]
        )
        
        # Search Analytics Component
        self.components["search_analytics"] = UIComponent(
            name="GoogleDriveSearchAnalytics",
            type="analytics_panel",
            props={
                "charts": [
                    {
                        "type": "search_history",
                        "title": "Search History",
                        "chart_type": "line",
                        "time_range": "7d",
                        "metric": "search_count"
                    },
                    {
                        "type": "popular_queries",
                        "title": "Popular Search Terms",
                        "chart_type": "bar",
                        "time_range": "30d",
                        "metric": "query_count"
                    },
                    {
                        "type": "search_performance",
                        "title": "Search Performance",
                        "chart_type": "area",
                        "time_range": "24h",
                        "metric": "response_time"
                    },
                    {
                        "type": "file_type_distribution",
                        "title": "File Type Distribution",
                        "chart_type": "pie",
                        "time_range": "all"
                    }
                ],
                "stats": [
                    {"label": "Total Searches", "key": "total_searches", "format": "number"},
                    {"label": "Unique Users", "key": "unique_users", "format": "number"},
                    {"label": "Avg Response Time", "key": "avg_response_time", "format": "duration"},
                    {"label": "Success Rate", "key": "success_rate", "format": "percentage"}
                ],
                "export": {
                    "enabled": True,
                    "formats": ["csv", "pdf"]
                }
            },
            styles={
                "background": "#ffffff",
                "border_radius": "8px",
                "padding": "20px"
            },
            events=["onChartClick", "onTimeRangeChange", "onExport"]
        )
    
    def get_component(self, component_name: str) -> Optional[UIComponent]:
        """Get component by name"""
        return self.components.get(component_name)
    
    def get_all_components(self) -> Dict[str, UIComponent]:
        """Get all components"""
        return self.components
    
    def get_react_component(self, component_name: str) -> Optional[str]:
        """Generate React component code"""
        
        component = self.get_component(component_name)
        if not component:
            return None
        
        if component_name == "search_bar":
            return self._generate_search_bar_react()
        elif component_name == "advanced_search":
            return self._generate_advanced_search_react()
        elif component_name == "search_results":
            return self._generate_search_results_react()
        elif component_name == "file_item":
            return self._generate_file_item_react()
        
        return None
    
    def get_vue_component(self, component_name: str) -> Optional[str]:
        """Generate Vue component code"""
        
        component = self.get_component(component_name)
        if not component:
            return None
        
        if component_name == "search_bar":
            return self._generate_search_bar_vue()
        elif component_name == "advanced_search":
            return self._generate_advanced_search_vue()
        elif component_name == "search_results":
            return self._generate_search_results_vue()
        elif component_name == "file_item":
            return self._generate_file_item_vue()
        
        return None
    
    def _generate_search_bar_react(self) -> str:
        """Generate React search bar component"""
        
        return '''
import React, { useState, useCallback, useEffect } from 'react';
import { Search, Mic, Settings, History } from 'lucide-react';

const GoogleDriveSearchBar = ({ 
  placeholder = "Search your Google Drive files...", 
  onSearch, 
  showVoiceSearch = true, 
  showAdvancedSearch = true,
  suggestions = [],
  onSuggestionSelect 
}) => {
  const [query, setQuery] = useState('');
  const [isFocused, setIsFocused] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [debouncedQuery, setDebouncedQuery] = useState('');

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(query);
    }, 300);
    return () => clearTimeout(timer);
  }, [query]);

  // Handle search
  const handleSearch = useCallback((searchQuery) => {
    onSearch?.(searchQuery);
    setShowSuggestions(false);
  }, [onSearch]);

  // Handle key press
  const handleKeyPress = useCallback((e) => {
    if (e.key === 'Enter') {
      handleSearch(query);
    } else if (e.key === 'Escape') {
      setShowSuggestions(false);
    }
  }, [query, handleSearch]);

  // Handle voice search
  const handleVoiceSearch = useCallback(() => {
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      const recognition = new SpeechRecognition();
      
      recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        setQuery(transcript);
        handleSearch(transcript);
      };
      
      recognition.start();
    }
  }, [handleSearch]);

  // Filter suggestions
  const filteredSuggestions = suggestions.filter(s => 
    s.text.toLowerCase().includes(query.toLowerCase())
  ).slice(0, 5);

  return (
    <div className="google-drive-search-bar" style={{
      position: 'relative',
      width: '100%',
      maxWidth: '800px',
      margin: '0 auto'
    }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        background: '#ffffff',
        border: '1px solid #e0e0e0',
        borderRadius: '8px',
        padding: '0 16px',
        boxShadow: isFocused ? '0 2px 8px rgba(0,0,0,0.1)' : 'none'
      }}>
        <Search size={20} color="#666" />
        
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyPress={handleKeyPress}
          onFocus={() => setIsFocused(true)}
          onBlur={() => {
            setTimeout(() => setIsFocused(false), 200);
            setTimeout(() => setShowSuggestions(false), 300);
          }}
          placeholder={placeholder}
          style={{
            flex: 1,
            border: 'none',
            outline: 'none',
            padding: '12px 8px',
            fontSize: '16px',
            background: 'transparent'
          }}
        />
        
        {showVoiceSearch && (
          <button
            onClick={handleVoiceSearch}
            style={{
              background: 'none',
              border: 'none',
              padding: '8px',
              cursor: 'pointer',
              borderRadius: '4px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}
            title="Voice Search"
          >
            <Mic size={18} color="#666" />
          </button>
        )}
        
        {showAdvancedSearch && (
          <button
            onClick={() => {/* Open advanced search */}}
            style={{
              background: 'none',
              border: 'none',
              padding: '8px',
              cursor: 'pointer',
              borderRadius: '4px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}
            title="Advanced Search"
          >
            <Settings size={18} color="#666" />
          </button>
        )}
      </div>

      {/* Suggestions Dropdown */}
      {showSuggestions && filteredSuggestions.length > 0 && (
        <div style={{
          position: 'absolute',
          top: '100%',
          left: 0,
          right: 0,
          background: '#ffffff',
          border: '1px solid #e0e0e0',
          borderTop: 'none',
          borderRadius: '0 0 8px 8px',
          boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
          zIndex: 1000,
          maxHeight: '300px',
          overflowY: 'auto'
        }}>
          {filteredSuggestions.map((suggestion, index) => (
            <div
              key={index}
              onClick={() => {
                setQuery(suggestion.text);
                handleSearch(suggestion.text);
                onSuggestionSelect?.(suggestion);
              }}
              style={{
                padding: '12px 16px',
                cursor: 'pointer',
                borderBottom: '1px solid #f0f0f0',
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
              }}
              onMouseEnter={(e) => e.target.style.background = '#f8f9fa'}
              onMouseLeave={(e) => e.target.style.background = '#ffffff'}
            >
              {suggestion.type === 'history' && <History size={14} color="#666" />}
              <span>{suggestion.text}</span>
              <span style={{
                marginLeft: 'auto',
                fontSize: '12px',
                color: '#999'
              }}>
                {suggestion.category}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default GoogleDriveSearchBar;
        '''
    
    def _generate_search_bar_vue(self) -> str:
        """Generate Vue search bar component"""
        
        return '''
<template>
  <div class="google-drive-search-bar" :style="containerStyle">
    <div class="search-input-container" :style="inputContainerStyle">
      <Search :size="20" color="#666" />
      
      <input
        ref="searchInput"
        v-model="query"
        @keyup.enter="handleSearch"
        @keyup.esc="showSuggestions = false"
        @focus="isFocused = true"
        @blur="handleBlur"
        :placeholder="placeholder"
        class="search-input"
      />
      
      <button
        v-if="showVoiceSearch"
        @click="handleVoiceSearch"
        class="action-button"
        title="Voice Search"
      >
        <Mic :size="18" color="#666" />
      </button>
      
      <button
        v-if="showAdvancedSearch"
        @click="$emit('openAdvancedSearch')"
        class="action-button"
        title="Advanced Search"
      >
        <Settings :size="18" color="#666" />
      </button>
    </div>

    <!-- Suggestions Dropdown -->
    <div
      v-show="showSuggestions && filteredSuggestions.length > 0"
      class="suggestions-dropdown"
    >
      <div
        v-for="(suggestion, index) in filteredSuggestions"
        :key="index"
        @click="selectSuggestion(suggestion)"
        class="suggestion-item"
        @mouseenter="hoveredIndex = index"
        @mouseleave="hoveredIndex = -1"
      >
        <History v-if="suggestion.type === 'history'" :size="14" color="#666" />
        <span>{{ suggestion.text }}</span>
        <span class="suggestion-category">{{ suggestion.category }}</span>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, watch, onMounted } from 'vue';
import { Search, Mic, Settings, History } from 'lucide-vue-next';

export default {
  name: 'GoogleDriveSearchBar',
  components: {
    Search,
    Mic,
    Settings,
    History
  },
  props: {
    placeholder: {
      type: String,
      default: "Search your Google Drive files..."
    },
    showVoiceSearch: {
      type: Boolean,
      default: true
    },
    showAdvancedSearch: {
      type: Boolean,
      default: true
    },
    suggestions: {
      type: Array,
      default: () => []
    }
  },
  emits: ['search', 'suggestionSelect', 'openAdvancedSearch'],
  setup(props, { emit }) {
    const query = ref('');
    const isFocused = ref(false);
    const showSuggestions = ref(false);
    const debouncedQuery = ref('');
    const hoveredIndex = ref(-1);
    const searchInput = ref(null);

    // Container styles
    const containerStyle = computed(() => ({
      position: 'relative',
      width: '100%',
      maxWidth: '800px',
      margin: '0 auto'
    }));

    const inputContainerStyle = computed(() => ({
      display: 'flex',
      alignItems: 'center',
      background: '#ffffff',
      border: '1px solid #e0e0e0',
      borderRadius: '8px',
      padding: '0 16px',
      boxShadow: isFocused.value ? '0 2px 8px rgba(0,0,0,0.1)' : 'none'
    }));

    // Filter suggestions
    const filteredSuggestions = computed(() => {
      return props.suggestions
        .filter(s => s.text.toLowerCase().includes(query.value.toLowerCase()))
        .slice(0, 5);
    });

    // Debounce search
    let debounceTimer;
    watch(query, (newQuery) => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        debouncedQuery.value = newQuery;
      }, 300);
    });

    // Handle search
    const handleSearch = () => {
      emit('search', query.value);
      showSuggestions.value = false;
    };

    // Handle blur
    const handleBlur = () => {
      setTimeout(() => {
        isFocused.value = false;
        showSuggestions.value = false;
      }, 200);
    };

    // Select suggestion
    const selectSuggestion = (suggestion) => {
      query.value = suggestion.text;
      handleSearch();
      emit('suggestionSelect', suggestion);
    };

    // Handle voice search
    const handleVoiceSearch = () => {
      if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        const recognition = new SpeechRecognition();
        
        recognition.onresult = (event) => {
          const transcript = event.results[0][0].transcript;
          query.value = transcript;
          handleSearch();
        };
        
        recognition.start();
      }
    };

    return {
      query,
      isFocused,
      showSuggestions,
      debouncedQuery,
      hoveredIndex,
      searchInput,
      containerStyle,
      inputContainerStyle,
      filteredSuggestions,
      handleSearch,
      handleBlur,
      selectSuggestion,
      handleVoiceSearch
    };
  }
};
</script>

<style scoped>
.google-drive-search-bar {
  position: relative;
}

.search-input-container {
  display: flex;
  align-items: center;
}

.search-input {
  flex: 1;
  border: none;
  outline: none;
  padding: 12px 8px;
  font-size: 16px;
  background: transparent;
}

.action-button {
  background: none;
  border: none;
  padding: 8px;
  cursor: pointer;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.action-button:hover {
  background: #f8f9fa;
}

.suggestions-dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  background: #ffffff;
  border: 1px solid #e0e0e0;
  border-top: none;
  border-radius: 0 0 8px 8px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
  z-index: 1000;
  max-height: 300px;
  overflow-y: auto;
}

.suggestion-item {
  padding: 12px 16px;
  cursor: pointer;
  border-bottom: 1px solid #f0f0f0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.suggestion-item:hover {
  background: #f8f9fa;
}

.suggestion-category {
  margin-left: auto;
  font-size: 12px;
  color: #999;
}
</style>
        '''
    
    def _generate_search_results_react(self) -> str:
        """Generate React search results component"""
        
        return '''
import React, { useState, useCallback, useMemo } from 'react';
import { ChevronDown, ChevronRight, Grid, List, Image, FileText, Calendar, FolderTree, Download, Share, Trash } from 'lucide-react';

const GoogleDriveSearchResults = ({
  results = [],
  loading = false,
  total = 0,
  view = 'list',
  onViewChange,
  onSort,
  sortField = 'relevance',
  sortOrder = 'desc',
  onItemClick,
  onItemSelect,
  selectedItems = [],
  onBulkAction,
  pagination = {},
  onPaginationChange
}) => {
  const [expandedFolders, setExpandedFolders] = useState({});

  // View type icons
  const viewIcons = {
    list: List,
    grid: Grid,
    thumbnail: Image,
    detail: FileText,
    timeline: Calendar,
    tree: FolderTree
  };

  // Sort results
  const sortedResults = useMemo(() => {
    const sorted = [...results].sort((a, b) => {
      let aVal = a[sortField];
      let bVal = b[sortField];
      
      if (typeof aVal === 'string') {
        aVal = aVal.toLowerCase();
        bVal = bVal.toLowerCase();
      }
      
      if (sortOrder === 'asc') {
        return aVal > bVal ? 1 : -1;
      } else {
        return aVal < bVal ? 1 : -1;
      }
    });
    return sorted;
  }, [results, sortField, sortOrder]);

  // Handle sort change
  const handleSort = useCallback((field) => {
    const newOrder = sortField === field && sortOrder === 'desc' ? 'asc' : 'desc';
    onSort?.(field, newOrder);
  }, [sortField, sortOrder, onSort]);

  // Format file size
  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  // Format date
  const formatDate = (dateString) => {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
  };

  // Get file icon
  const getFileIcon = (mimeType) => {
    if (mimeType.startsWith('image/')) return '🖼️';
    if (mimeType.startsWith('video/')) return '🎬';
    if (mimeType.startsWith('audio/')) return '🎵';
    if (mimeType.startsWith('application/pdf')) return '📄';
    if (mimeType.includes('document')) return '📝';
    if (mimeType.includes('spreadsheet')) return '📊';
    if (mimeType.includes('presentation')) return '📽️';
    return '📄';
  };

  // Render list view
  const renderListView = () => (
    <div className="results-list">
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ background: '#f8f9fa' }}>
            <th style={{ padding: '12px', textAlign: 'left', cursor: 'pointer' }} onClick={() => handleSort('name')}>
              Name {sortField === 'name' && (sortOrder === 'asc' ? '↑' : '↓')}
            </th>
            <th style={{ padding: '12px', textAlign: 'left', cursor: 'pointer' }} onClick={() => handleSort('modified_time')}>
              Modified {sortField === 'modified_time' && (sortOrder === 'asc' ? '↑' : '↓')}
            </th>
            <th style={{ padding: '12px', textAlign: 'left', cursor: 'pointer' }} onClick={() => handleSort('size')}>
              Size {sortField === 'size' && (sortOrder === 'asc' ? '↑' : '↓')}
            </th>
            <th style={{ padding: '12px', textAlign: 'left' }}>Owner</th>
            <th style={{ padding: '12px', textAlign: 'left' }}>Actions</th>
          </tr>
        </thead>
        <tbody>
          {sortedResults.map((result) => (
            <tr key={result.id} style={{ borderBottom: '1px solid #f0f0f0' }}>
              <td style={{ padding: '12px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontSize: '18px' }}>{getFileIcon(result.mime_type)}</span>
                  <a
                    href={result.url}
                    onClick={() => onItemClick?.(result)}
                    style={{ 
                      color: '#4285F4', 
                      textDecoration: 'none',
                      fontWeight: '500'
                    }}
                  >
                    {result.title}
                  </a>
                </div>
              </td>
              <td style={{ padding: '12px', color: '#666' }}>
                {formatDate(result.updated_at)}
              </td>
              <td style={{ padding: '12px', color: '#666' }}>
                {formatFileSize(result.size)}
              </td>
              <td style={{ padding: '12px', color: '#666' }}>
                {result.metadata.owners?.[0] || ''}
              </td>
              <td style={{ padding: '12px' }}>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button
                    onClick={() => window.open(result.download_url, '_blank')}
                    style={{
                      background: 'none',
                      border: 'none',
                      cursor: 'pointer',
                      padding: '4px'
                    }}
                    title="Download"
                  >
                    <Download size={16} color="#666" />
                  </button>
                  <button
                    onClick={() => {/* Handle share */}}
                    style={{
                      background: 'none',
                      border: 'none',
                      cursor: 'pointer',
                      padding: '4px'
                    }}
                    title="Share"
                  >
                    <Share size={16} color="#666" />
                  </button>
                  <button
                    onClick={() => {/* Handle delete */}}
                    style={{
                      background: 'none',
                      border: 'none',
                      cursor: 'pointer',
                      padding: '4px'
                    }}
                    title="Delete"
                  >
                    <Trash size={16} color="#666" />
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

  // Render grid view
  const renderGridView = () => (
    <div className="results-grid" style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
      gap: '16px',
      padding: '16px 0'
    }}>
      {sortedResults.map((result) => (
        <div
          key={result.id}
          onClick={() => onItemClick?.(result)}
          style={{
            background: '#ffffff',
            border: '1px solid #e0e0e0',
            borderRadius: '8px',
            padding: '16px',
            cursor: 'pointer',
            transition: 'all 0.2s'
          }}
          onMouseEnter={(e) => {
            e.target.style.boxShadow = '0 4px 12px rgba(0,0,0,0.1)';
            e.target.style.transform = 'translateY(-2px)';
          }}
          onMouseLeave={(e) => {
            e.target.style.boxShadow = 'none';
            e.target.style.transform = 'translateY(0)';
          }}
        >
          <div style={{
            fontSize: '32px',
            textAlign: 'center',
            marginBottom: '12px'
          }}>
            {getFileIcon(result.mime_type)}
          </div>
          <div style={{
            fontSize: '14px',
            fontWeight: '500',
            textAlign: 'center',
            marginBottom: '8px',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap'
          }}>
            {result.title}
          </div>
          <div style={{
            fontSize: '12px',
            color: '#666',
            textAlign: 'center'
          }}>
            {formatFileSize(result.size)}
          </div>
        </div>
      ))}
    </div>
  );

  return (
    <div className="google-drive-search-results">
      {/* View Controls */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '16px 0',
        borderBottom: '1px solid #e0e0e0'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ fontSize: '14px', color: '#666' }}>
            {total} results
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            {Object.entries(viewIcons).map(([viewType, Icon]) => (
              <button
                key={viewType}
                onClick={() => onViewChange?.(viewType)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  padding: '8px 12px',
                  border: view === viewType ? '1px solid #4285F4' : '1px solid #e0e0e0',
                  borderRadius: '6px',
                  background: view === viewType ? '#e8f0fe' : '#ffffff',
                  cursor: 'pointer'
                }}
              >
                <Icon size={16} color={view === viewType ? '#4285F4' : '#666'} />
                <span style={{ fontSize: '12px', color: view === viewType ? '#4285F4' : '#666' }}>
                  {viewType.charAt(0).toUpperCase() + viewType.slice(1)}
                </span>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Results */}
      <div style={{ minHeight: '400px' }}>
        {loading ? (
          <div style={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            height: '200px'
          }}>
            <div>Loading...</div>
          </div>
        ) : results.length === 0 ? (
          <div style={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            height: '200px',
            color: '#666'
          }}>
            No results found
          </div>
        ) : (
          <>
            {view === 'list' && renderListView()}
            {view === 'grid' && renderGridView()}
            {/* Add other view types as needed */}
          </>
        )}
      </div>

      {/* Pagination */}
      {pagination && (
        <div style={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          gap: '8px',
          padding: '16px 0'
        }}>
          <button
            onClick={() => onPaginationChange?.(pagination.page - 1)}
            disabled={pagination.page <= 1}
            style={{
              padding: '8px 12px',
              border: '1px solid #e0e0e0',
              borderRadius: '4px',
              background: '#ffffff',
              cursor: pagination.page > 1 ? 'pointer' : 'not-allowed',
              opacity: pagination.page > 1 ? 1 : 0.5
            }}
          >
            Previous
          </button>
          
          <span style={{ fontSize: '14px', color: '#666' }}>
            Page {pagination.page} of {Math.ceil(total / pagination.pageSize)}
          </span>
          
          <button
            onClick={() => onPaginationChange?.(pagination.page + 1)}
            disabled={pagination.page >= Math.ceil(total / pagination.pageSize)}
            style={{
              padding: '8px 12px',
              border: '1px solid #e0e0e0',
              borderRadius: '4px',
              background: '#ffffff',
              cursor: pagination.page < Math.ceil(total / pagination.pageSize) ? 'pointer' : 'not-allowed',
              opacity: pagination.page < Math.ceil(total / pagination.pageSize) ? 1 : 0.5
            }}
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
};

export default GoogleDriveSearchResults;
        '''
    
    def _generate_file_item_react(self) -> str:
        """Generate React file item component"""
        
        return '''
import React, { useState } from 'react';
import { Download, Share, Trash, Edit, Copy, Folder, Star, Info, Robot, MoreHorizontal } from 'lucide-react';

const GoogleDriveFileItem = ({
  file,
  isSelected = false,
  onSelect,
  onClick,
  onAction,
  showCheckbox = true,
  showThumbnail = true,
  showActions = true
}) => {
  const [showContextMenu, setShowContextMenu] = useState(false);

  // Get file icon
  const getFileIcon = (mimeType) => {
    if (mimeType.startsWith('image/')) return '🖼️';
    if (mimeType.startsWith('video/')) return '🎬';
    if (mimeType.startsWith('audio/')) return '🎵';
    if (mimeType.startsWith('application/pdf')) return '📄';
    if (mimeType.includes('document')) return '📝';
    if (mimeType.includes('spreadsheet')) return '📊';
    if (mimeType.includes('presentation')) return '📽️';
    return '📄';
  };

  // Format file size
  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  // Handle action
  const handleAction = (action, event) => {
    event.stopPropagation();
    onAction?.(action, file);
  };

  // Handle context menu
  const handleContextMenu = (event) => {
    event.preventDefault();
    setShowContextMenu(true);
  };

  // Context menu items
  const contextMenuItems = [
    { action: 'open', label: 'Open', icon: Folder },
    { action: 'download', label: 'Download', icon: Download },
    { action: 'copy', label: 'Make a copy', icon: Copy },
    { action: 'rename', label: 'Rename', icon: Edit },
    { action: 'share', label: 'Share', icon: Share },
    { action: 'add_star', label: 'Add to Starred', icon: Star },
    { action: 'details', label: 'View details', icon: Info },
    { action: 'add_to_workflow', label: 'Add to Workflow', icon: Robot },
    { action: 'delete', label: 'Delete', icon: Trash, danger: true }
  ];

  return (
    <>
      <div
        className={`google-drive-file-item ${isSelected ? 'selected' : ''}`}
        onClick={() => onClick?.(file)}
        onContextMenu={handleContextMenu}
        style={{
          display: 'flex',
          alignItems: 'center',
          padding: '12px 16px',
          borderBottom: '1px solid #f0f0f0',
          cursor: 'pointer',
          background: isSelected ? '#e8f0fe' : 'transparent',
          transition: 'background 0.2s'
        }}
        onMouseEnter={(e) => {
          if (!isSelected) {
            e.target.style.background = '#f8f9fa';
          }
        }}
        onMouseLeave={(e) => {
          if (!isSelected) {
            e.target.style.background = 'transparent';
          }
        }}
      >
        {/* Checkbox */}
        {showCheckbox && (
          <input
            type="checkbox"
            checked={isSelected}
            onChange={(e) => {
              e.stopPropagation();
              onSelect?.(file, e.target.checked);
            }}
            style={{
              marginRight: '12px',
              cursor: 'pointer'
            }}
          />
        )}

        {/* Thumbnail/File Icon */}
        <div style={{
          width: '40px',
          height: '40px',
          marginRight: '12px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: '24px',
          background: file.thumbnail_url ? `url(${file.thumbnail_url})` : 'transparent',
          backgroundSize: 'cover',
          backgroundPosition: 'center',
          borderRadius: '4px'
        }}>
          {!file.thumbnail_url && getFileIcon(file.mime_type)}
        </div>

        {/* File Info */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{
            fontSize: '14px',
            fontWeight: '500',
            marginBottom: '4px',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap'
          }}>
            {file.title}
          </div>
          <div style={{
            fontSize: '12px',
            color: '#666',
            display: 'flex',
            gap: '16px'
          }}>
            <span>{formatFileSize(file.size)}</span>
            <span>{new Date(file.updated_at).toLocaleDateString()}</span>
            <span>{file.metadata.owners?.[0] || ''}</span>
          </div>
        </div>

        {/* Action Buttons */}
        {showActions && (
          <div style={{
            display: 'flex',
            gap: '4px',
            marginLeft: '12px'
          }}>
            <button
              onClick={(e) => handleAction('download', e)}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: '32px',
                height: '32px',
                border: 'none',
                background: 'none',
                cursor: 'pointer',
                borderRadius: '4px',
                padding: '0'
              }}
              title="Download"
            >
              <Download size={16} color="#666" />
            </button>
            
            <button
              onClick={(e) => handleAction('share', e)}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: '32px',
                height: '32px',
                border: 'none',
                background: 'none',
                cursor: 'pointer',
                borderRadius: '4px',
                padding: '0'
              }}
              title="Share"
            >
              <Share size={16} color="#666" />
            </button>
            
            <button
              onClick={(e) => handleAction('more', e)}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: '32px',
                height: '32px',
                border: 'none',
                background: 'none',
                cursor: 'pointer',
                borderRadius: '4px',
                padding: '0'
              }}
              title="More actions"
            >
              <MoreHorizontal size={16} color="#666" />
            </button>
          </div>
        )}
      </div>

      {/* Context Menu */}
      {showContextMenu && (
        <div
          className="context-menu"
          style={{
            position: 'fixed',
            background: '#ffffff',
            border: '1px solid #e0e0e0',
            borderRadius: '8px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
            zIndex: 1000,
            minWidth: '200px'
          }}
          onMouseLeave={() => setShowContextMenu(false)}
        >
          {contextMenuItems.map((item, index) => {
            const Icon = item.icon;
            return (
              <div
                key={index}
                onClick={(e) => {
                  handleAction(item.action, e);
                  setShowContextMenu(false);
                }}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px',
                  padding: '12px 16px',
                  cursor: 'pointer',
                  borderBottom: index < contextMenuItems.length - 1 ? '1px solid #f0f0f0' : 'none',
                  color: item.danger ? '#dc3545' : '#333'
                }}
                onMouseEnter={(e) => e.target.style.background = '#f8f9fa'}
                onMouseLeave={(e) => e.target.style.background = '#ffffff'}
              >
                <Icon size={16} />
                <span>{item.label}</span>
              </div>
            );
          })}
        </div>
      )}
    </>
  );
};

export default GoogleDriveFileItem;
        '''
    
    def generate_css_styles(self) -> str:
        """Generate CSS styles for Google Drive search UI"""
        
        return '''
/* Google Drive Search UI Styles */

/* Search Bar */
.google-drive-search-bar {
  position: relative;
  width: 100%;
  max-width: 800px;
  margin: 0 auto;
}

.google-drive-search-bar .search-input-container {
  display: flex;
  align-items: center;
  background: #ffffff;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 0 16px;
  box-shadow: none;
  transition: box-shadow 0.2s ease;
}

.google-drive-search-bar .search-input-container:focus-within {
  box-shadow: 0 2px 8px rgba(66, 133, 244, 0.1);
  border-color: #4285F4;
}

.google-drive-search-bar .search-input {
  flex: 1;
  border: none;
  outline: none;
  padding: 12px 8px;
  font-size: 16px;
  background: transparent;
}

.google-drive-search-bar .action-button {
  background: none;
  border: none;
  padding: 8px;
  cursor: pointer;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background-color 0.2s ease;
}

.google-drive-search-bar .action-button:hover {
  background: #f8f9fa;
}

/* Suggestions Dropdown */
.suggestions-dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  background: #ffffff;
  border: 1px solid #e0e0e0;
  border-top: none;
  border-radius: 0 0 8px 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  z-index: 1000;
  max-height: 300px;
  overflow-y: auto;
}

.suggestion-item {
  padding: 12px 16px;
  cursor: pointer;
  border-bottom: 1px solid #f0f0f0;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: background-color 0.2s ease;
}

.suggestion-item:hover {
  background: #f8f9fa;
}

.suggestion-category {
  margin-left: auto;
  font-size: 12px;
  color: #999;
}

/* Search Results */
.google-drive-search-results {
  background: #ffffff;
  border-radius: 8px;
  border: 1px solid #e0e0e0;
}

.results-list table {
  width: 100%;
  border-collapse: collapse;
}

.results-list th,
.results-list td {
  padding: 12px;
  text-align: left;
}

.results-list th {
  background: #f8f9fa;
  font-weight: 600;
  color: #333;
  cursor: pointer;
  user-select: none;
}

.results-list th:hover {
  background: #e9ecef;
}

.results-list tr {
  border-bottom: 1px solid #f0f0f0;
  transition: background-color 0.2s ease;
}

.results-list tr:hover {
  background: #f8f9fa;
}

.results-list tr.selected {
  background: #e8f0fe;
}

/* Grid View */
.results-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 16px;
  padding: 16px 0;
}

.grid-item {
  background: #ffffff;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 16px;
  cursor: pointer;
  transition: all 0.2s ease;
  text-align: center;
}

.grid-item:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  transform: translateY(-2px);
}

.grid-item-icon {
  font-size: 32px;
  margin-bottom: 12px;
}

.grid-item-title {
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 8px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.grid-item-size {
  font-size: 12px;
  color: #666;
}

/* File Item */
.google-drive-file-item {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid #f0f0f0;
  cursor: pointer;
  transition: background-color 0.2s ease;
}

.google-drive-file-item:hover {
  background: #f8f9fa;
}

.google-drive-file-item.selected {
  background: #e8f0fe;
}

.file-item-icon {
  width: 40px;
  height: 40px;
  margin-right: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  background-size: cover;
  background-position: center;
  border-radius: 4px;
}

.file-item-info {
  flex: 1;
  min-width: 0;
}

.file-item-title {
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-item-meta {
  font-size: 12px;
  color: #666;
  display: flex;
  gap: 16px;
}

.file-item-actions {
  display: flex;
  gap: 4px;
  margin-left: 12px;
}

.action-button {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: none;
  background: none;
  cursor: pointer;
  border-radius: 4px;
  padding: 0;
  transition: background-color 0.2s ease;
}

.action-button:hover {
  background: #f8f9fa;
}

/* Context Menu */
.context-menu {
  position: fixed;
  background: #ffffff;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  z-index: 1000;
  min-width: 200px;
}

.context-menu-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  cursor: pointer;
  transition: background-color 0.2s ease;
  color: #333;
}

.context-menu-item:hover {
  background: #f8f9fa;
}

.context-menu-item.danger {
  color: #dc3545;
}

.context-menu-separator {
  height: 1px;
  background: #e0e0e0;
  margin: 4px 0;
}

/* Responsive Design */
@media (max-width: 768px) {
  .google-drive-search-bar {
    max-width: 100%;
  }
  
  .results-grid {
    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
    gap: 12px;
  }
  
  .file-item-meta {
    flex-direction: column;
    gap: 4px;
  }
  
  .file-item-actions {
    flex-direction: column;
    gap: 8px;
  }
}

@media (max-width: 480px) {
  .results-list th,
  .results-list td {
    padding: 8px;
    font-size: 14px;
  }
  
  .grid-item {
    padding: 12px;
  }
  
  .google-drive-file-item {
    padding: 8px 12px;
  }
}

/* Animation Classes */
.fade-in {
  animation: fadeIn 0.3s ease-in;
}

.slide-down {
  animation: slideDown 0.3s ease-out;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

@keyframes slideDown {
  from {
    transform: translateY(-10px);
    opacity: 0;
  }
  to {
    transform: translateY(0);
    opacity: 1;
  }
}

/* Google Drive Theme Colors */
.google-drive-primary {
  color: #4285F4;
}

.google-drive-primary-light {
  background: #e8f0fe;
}

.google-drive-primary-dark {
  background: #4285F4;
}

.google-drive-text {
  color: #202124;
}

.google-drive-text-secondary {
  color: #5f6368;
}

.google-drive-text-disabled {
  color: #9aa0a6;
}

.google-drive-border {
  border-color: #dadce0;
}

.google-drive-background {
  background: #ffffff;
}

.google-drive-surface {
  background: #f8f9fa;
}
        '''

# Export the components and utilities
__all__ = [
    "GoogleDriveSearchComponents",
    "UIComponent"
]