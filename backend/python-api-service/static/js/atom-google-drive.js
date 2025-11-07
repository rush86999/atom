/**
 * ATOM Google Drive Integration - Frontend JavaScript
 * Complete frontend application for Google Drive automation
 */

class AtomGoogleDriveApp {
    constructor() {
        this.config = {
            apiBaseUrl: window.location.origin + '/api/google-drive',
            automationApiUrl: window.location.origin + '/api/google-drive/automation',
            maxRetries: 3,
            retryDelay: 1000,
            defaultPageSize: 50,
            currentFolder: 'root',
            currentSection: 'dashboard',
            searchType: 'semantic',
            liveUpdatesEnabled: true
        };

        this.state = {
            user: null,
            session: null,
            authenticated: false,
            files: [],
            workflows: [],
            executions: [],
            currentFolder: 'root',
            searchResults: [],
            syncStatus: 'synced',
            lastSyncTime: null,
            liveEvents: []
        };

        this.elements = {};
        this.eventListeners = {};
        this.init();
    }

    // Initialize application
    async init() {
        try {
            console.log('Initializing ATOM Google Drive App...');
            
            // Cache DOM elements
            this.cacheElements();
            
            // Initialize event listeners
            this.initEventListeners();
            
            // Check authentication status
            await this.checkAuthentication();
            
            // Initialize UI
            this.initializeUI();
            
            // Start live updates
            if (this.state.authenticated) {
                this.startLiveUpdates();
            }
            
            console.log('ATOM Google Drive App initialized successfully');
            
        } catch (error) {
            console.error('Failed to initialize app:', error);
            this.showError('Failed to initialize application. Please refresh the page.');
        }
    }

    // Cache DOM elements
    cacheElements() {
        this.elements = {
            // Navigation
            navLinks: document.querySelectorAll('[data-section]'),
            userName: document.getElementById('userName'),
            
            // Auth modal
            authModal: document.getElementById('authModal'),
            connectGoogleBtn: document.getElementById('connectGoogleBtn'),
            
            // Dashboard
            totalFilesStat: document.getElementById('totalFilesStat'),
            processedFilesStat: document.getElementById('processedFilesStat'),
            activeWorkflowsStat: document.getElementById('activeWorkflowsStat'),
            syncStatusStat: document.getElementById('syncStatusStat'),
            recentActivityList: document.getElementById('recentActivityList'),
            systemStatusList: document.getElementById('systemStatusList'),
            
            // Quick actions
            quickSearchBtn: document.getElementById('quickSearchBtn'),
            quickUploadBtn: document.getElementById('quickUploadBtn'),
            quickWorkflowBtn: document.getElementById('quickWorkflowBtn'),
            quickSyncBtn: document.getElementById('quickSyncBtn'),
            
            // Files
            filesTable: document.getElementById('filesTable'),
            filesTableBody: document.getElementById('filesTableBody'),
            fileBreadcrumb: document.getElementById('fileBreadcrumb'),
            refreshFilesBtn: document.getElementById('refreshFilesBtn'),
            uploadFilesBtn: document.getElementById('uploadFilesBtn'),
            selectAllFiles: document.getElementById('selectAllFiles'),
            
            // Search
            searchInput: document.getElementById('searchInput'),
            searchBtn: document.getElementById('searchBtn'),
            searchSuggestions: document.getElementById('searchSuggestions'),
            searchSuggestionsList: document.getElementById('searchSuggestionsList'),
            searchResultsList: document.getElementById('searchResultsList'),
            searchResultsGrid: document.getElementById('searchResultsGrid'),
            searchInfo: document.getElementById('searchInfo'),
            searchInfoText: document.getElementById('searchInfoText'),
            
            // Automation
            createWorkflowBtn: document.getElementById('createWorkflowBtn'),
            workflowsTable: document.getElementById('workflowsTable'),
            workflowsTableBody: document.getElementById('workflowsTableBody'),
            executionsTable: document.getElementById('executionsTable'),
            executionsTableBody: document.getElementById('executionsTableBody'),
            webhooksTable: document.getElementById('webhooksTable'),
            webhooksTableBody: document.getElementById('webhooksTableBody'),
            
            // Sync
            syncIndicator: document.getElementById('syncIndicator'),
            syncStatusText: document.getElementById('syncStatusText'),
            lastSyncTime: document.getElementById('lastSyncTime'),
            filesSyncedCount: document.getElementById('filesSyncedCount'),
            embeddingsCount: document.getElementById('embeddingsCount'),
            syncQueueCount: document.getElementById('syncQueueCount'),
            manualSyncBtn: document.getElementById('manualSyncBtn'),
            liveEventsContainer: document.getElementById('liveEventsContainer'),
            liveEventsToggle: document.getElementById('liveEventsToggle'),
            
            // Modals
            workflowEditorModal: document.getElementById('workflowEditorModal'),
            fileUploadModal: document.getElementById('fileUploadModal'),
            
            // Loading
            loadingOverlay: document.getElementById('loadingOverlay'),
            
            // Toast
            toastContainer: document.getElementById('toastContainer')
        };
    }

    // Initialize event listeners
    initEventListeners() {
        // Navigation
        this.elements.navLinks.forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const section = link.dataset.section;
                this.switchSection(section);
            });
        });

        // Authentication
        if (this.elements.connectGoogleBtn) {
            this.elements.connectGoogleBtn.addEventListener('click', () => {
                this.authenticate();
            });
        }

        // Quick actions
        if (this.elements.quickSearchBtn) {
            this.elements.quickSearchBtn.addEventListener('click', () => {
                this.switchSection('search');
                this.elements.searchInput.focus();
            });
        }

        if (this.elements.quickUploadBtn) {
            this.elements.quickUploadBtn.addEventListener('click', () => {
                this.showFileUploadModal();
            });
        }

        if (this.elements.quickWorkflowBtn) {
            this.elements.quickWorkflowBtn.addEventListener('click', () => {
                this.showWorkflowEditor();
            });
        }

        if (this.elements.quickSyncBtn) {
            this.elements.quickSyncBtn.addEventListener('click', () => {
                this.manualSync();
            });
        }

        // File operations
        if (this.elements.refreshFilesBtn) {
            this.elements.refreshFilesBtn.addEventListener('click', () => {
                this.loadFiles();
            });
        }

        if (this.elements.uploadFilesBtn) {
            this.elements.uploadFilesBtn.addEventListener('click', () => {
                this.showFileUploadModal();
            });
        }

        if (this.elements.selectAllFiles) {
            this.elements.selectAllFiles.addEventListener('change', (e) => {
                this.toggleSelectAllFiles(e.target.checked);
            });
        }

        // Search
        if (this.elements.searchInput) {
            this.elements.searchInput.addEventListener('input', (e) => {
                this.handleSearchInput(e.target.value);
            });

            this.elements.searchInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    this.performSearch();
                }
            });
        }

        if (this.elements.searchBtn) {
            this.elements.searchBtn.addEventListener('click', () => {
                this.performSearch();
            });
        }

        // Automation
        if (this.elements.createWorkflowBtn) {
            this.elements.createWorkflowBtn.addEventListener('click', () => {
                this.showWorkflowEditor();
            });
        }

        // Sync
        if (this.elements.manualSyncBtn) {
            this.elements.manualSyncBtn.addEventListener('click', () => {
                this.manualSync();
            });
        }

        if (this.elements.liveEventsToggle) {
            this.elements.liveEventsToggle.addEventListener('change', (e) => {
                this.config.liveUpdatesEnabled = e.target.checked;
                if (this.config.liveUpdatesEnabled) {
                    this.startLiveUpdates();
                } else {
                    this.stopLiveUpdates();
                }
            });
        }

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            this.handleKeyboardShortcuts(e);
        });
    }

    // Authentication
    async checkAuthentication() {
        try {
            const sessionId = this.getSessionId();
            if (!sessionId) {
                this.showAuthModal();
                return;
            }

            const response = await this.makeApiCall('/auth/validate', {
                method: 'POST',
                body: JSON.stringify({ session_id: sessionId })
            });

            if (response.success && response.valid) {
                this.state.authenticated = true;
                this.state.session = response.session;
                this.state.user = response.session.user;
                
                this.updateUserDisplay();
                this.hideAuthModal();
                
                // Load initial data
                await this.loadDashboardData();
                
            } else {
                this.showAuthModal();
            }
        } catch (error) {
            console.error('Authentication check failed:', error);
            this.showAuthModal();
        }
    }

    async authenticate() {
        try {
            const response = await this.makeApiCall('/auth/start', {
                method: 'POST',
                body: JSON.stringify({
                    redirect_uri: window.location.origin
                })
            });

            if (response.success && response.authorization_url) {
                // Open Google OAuth in popup
                const popup = window.open(
                    response.authorization_url,
                    'google_auth',
                    'width=500,height=600,scrollbars=yes,resizable=yes'
                );

                // Listen for popup close
                const checkClosed = setInterval(() => {
                    if (popup.closed) {
                        clearInterval(checkClosed);
                        // Check authentication status after popup closes
                        this.checkAuthentication();
                    }
                }, 1000);
            } else {
                this.showError('Failed to start authentication process');
            }
        } catch (error) {
            console.error('Authentication failed:', error);
            this.showError('Authentication failed. Please try again.');
        }
    }

    async logout() {
        try {
            const sessionId = this.getSessionId();
            if (sessionId) {
                await this.makeApiCall('/auth/invalidate', {
                    method: 'POST',
                    body: JSON.stringify({ session_id: sessionId })
                });
            }

            // Clear local storage
            localStorage.removeItem('atom_session_id');
            
            // Reset state
            this.state.authenticated = false;
            this.state.session = null;
            this.state.user = null;
            
            // Show auth modal
            this.showAuthModal();
            
            this.showSuccess('Logged out successfully');
            
        } catch (error) {
            console.error('Logout failed:', error);
            this.showError('Logout failed');
        }
    }

    // Session management
    getSessionId() {
        return localStorage.getItem('atom_session_id');
    }

    setSessionId(sessionId) {
        localStorage.setItem('atom_session_id', sessionId);
    }

    // UI Management
    showAuthModal() {
        if (this.elements.authModal) {
            const modal = new bootstrap.Modal(this.elements.authModal);
            modal.show();
        }
    }

    hideAuthModal() {
        if (this.elements.authModal) {
            const modal = bootstrap.Modal.getInstance(this.elements.authModal);
            if (modal) {
                modal.hide();
            }
        }
    }

    showFileUploadModal() {
        if (this.elements.fileUploadModal) {
            const modal = new bootstrap.Modal(this.elements.fileUploadModal);
            modal.show();
        }
    }

    showWorkflowEditor(workflow = null) {
        if (this.elements.workflowEditorModal) {
            const modal = new bootstrap.Modal(this.elements.workflowEditorModal);
            
            // Initialize workflow editor
            this.initWorkflowEditor(workflow);
            
            modal.show();
        }
    }

    updateUserDisplay() {
        if (this.elements.userName && this.state.user) {
            this.elements.userName.textContent = this.state.user.name || 'User';
        }
    }

    // Section management
    switchSection(sectionName) {
        try {
            // Hide all sections
            document.querySelectorAll('.content-section').forEach(section => {
                section.style.display = 'none';
            });

            // Show target section
            const targetSection = document.getElementById(`${sectionName}-section`);
            if (targetSection) {
                targetSection.style.display = 'block';
            }

            // Update navigation active state
            this.elements.navLinks.forEach(link => {
                link.classList.remove('active');
                if (link.dataset.section === sectionName) {
                    link.classList.add('active');
                }
            });

            this.config.currentSection = sectionName;

            // Load section-specific data
            this.loadSectionData(sectionName);
            
        } catch (error) {
            console.error('Failed to switch section:', error);
            this.showError('Failed to switch to section');
        }
    }

    async loadSectionData(sectionName) {
        try {
            switch (sectionName) {
                case 'dashboard':
                    await this.loadDashboardData();
                    break;
                case 'files':
                    await this.loadFiles();
                    break;
                case 'search':
                    // Search section data loaded on demand
                    break;
                case 'automation':
                    await this.loadAutomationData();
                    break;
                case 'sync':
                    await this.loadSyncData();
                    break;
            }
        } catch (error) {
            console.error(`Failed to load ${sectionName} data:`, error);
        }
    }

    // Dashboard data
    async loadDashboardData() {
        try {
            const [statsResponse, activityResponse] = await Promise.all([
                this.makeApiCall('/automation/automation-stats'),
                this.loadRecentActivity()
            ]);

            if (statsResponse.success) {
                this.updateDashboardStats(statsResponse.stats);
            }

        } catch (error) {
            console.error('Failed to load dashboard data:', error);
        }
    }

    updateDashboardStats(stats) {
        // Update automation engine stats
        if (stats.automation_engine) {
            const engineStats = stats.automation_engine;
            
            if (this.elements.activeWorkflowsStat) {
                this.elements.activeWorkflowsStat.textContent = 
                    engineStats.enabled_workflows || 0;
            }
        }

        // Update action system stats
        if (stats.action_system) {
            const actionStats = stats.action_system;
            
            if (this.elements.totalFilesStat) {
                this.elements.totalFilesStat.textContent = 
                    actionStats.total_actions || 0; // This would need to be adjusted
            }
        }

        // Update trigger system stats
        if (stats.trigger_system) {
            const triggerStats = stats.trigger_system;
            
            if (this.elements.processedFilesStat) {
                this.elements.processedFilesStat.textContent = 
                    triggerStats.processed_events || 0;
            }
        }

        // Update sync status
        if (this.elements.syncStatusStat) {
            this.elements.syncStatusStat.textContent = 'Connected';
        }
    }

    // Files management
    async loadFiles(folderId = null) {
        try {
            this.showLoading();
            
            const targetFolder = folderId || this.state.currentFolder;
            
            const response = await this.makeApiCall('/files', {
                queryParams: {
                    q: targetFolder === 'root' ? '' : `'${targetFolder}' in parents`,
                    fields: 'files(id,name,mimeType,size,modifiedTime,owners,webViewLink)',
                    pageSize: this.config.defaultPageSize
                }
            });

            if (response.success) {
                this.state.files = response.files || [];
                this.renderFilesList();
                this.updateBreadcrumb(targetFolder);
            } else {
                throw new Error(response.error || 'Failed to load files');
            }

        } catch (error) {
            console.error('Failed to load files:', error);
            this.showError('Failed to load files. Please try again.');
        } finally {
            this.hideLoading();
        }
    }

    renderFilesList() {
        if (!this.elements.filesTableBody) return;

        this.elements.filesTableBody.innerHTML = '';

        if (this.state.files.length === 0) {
            this.elements.filesTableBody.innerHTML = `
                <tr>
                    <td colspan="7" class="text-center text-muted">
                        <i class="fas fa-folder-open fa-3x mb-2"></i>
                        <p>This folder is empty</p>
                    </td>
                </tr>
            `;
            return;
        }

        this.state.files.forEach(file => {
            const row = this.createFileRow(file);
            this.elements.filesTableBody.appendChild(row);
        });
    }

    createFileRow(file) {
        const tr = document.createElement('tr');
        tr.dataset.fileId = file.id;

        const isFolder = file.mimeType === 'application/vnd.google-apps.folder';
        const icon = this.getFileIcon(file.mimeType);
        const size = this.formatFileSize(file.size);

        tr.innerHTML = `
            <td>
                <input type="checkbox" class="file-checkbox" data-file-id="${file.id}">
            </td>
            <td>
                <div class="d-flex align-items-center">
                    <i class="${icon} me-2"></i>
                    <a href="#" class="file-link text-decoration-none" data-file-id="${file.id}">
                        ${file.name}
                    </a>
                </div>
            </td>
            <td>${isFolder ? '-' : size}</td>
            <td>${this.formatDate(file.modifiedTime)}</td>
            <td>${file.owners?.[0]?.displayName || 'Unknown'}</td>
            <td>
                <span class="badge bg-success">Synced</span>
            </td>
            <td>
                <div class="btn-group btn-group-sm">
                    <button class="btn btn-outline-primary btn-sm file-action" 
                            data-action="download" data-file-id="${file.id}">
                        <i class="fas fa-download"></i>
                    </button>
                    <button class="btn btn-outline-info btn-sm file-action" 
                            data-action="share" data-file-id="${file.id}">
                        <i class="fas fa-share"></i>
                    </button>
                    <button class="btn btn-outline-secondary btn-sm file-action" 
                            data-action="process" data-file-id="${file.id}">
                        <i class="fas fa-cogs"></i>
                    </button>
                </div>
            </td>
        `;

        // Add event listeners
        const fileLink = tr.querySelector('.file-link');
        if (fileLink) {
            fileLink.addEventListener('click', (e) => {
                e.preventDefault();
                if (isFolder) {
                    this.loadFiles(file.id);
                } else {
                    this.openFile(file);
                }
            });
        }

        const actionButtons = tr.querySelectorAll('.file-action');
        actionButtons.forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                const action = btn.dataset.action;
                const fileId = btn.dataset.fileId;
                this.handleFileAction(action, fileId, file);
            });
        });

        return tr;
    }

    handleFileAction(action, fileId, file) {
        switch (action) {
            case 'download':
                this.downloadFile(fileId, file.name);
                break;
            case 'share':
                this.shareFile(fileId);
                break;
            case 'process':
                this.processFile(fileId);
                break;
        }
    }

    // Search functionality
    async handleSearchInput(query) {
        if (query.length < 2) {
            this.hideSearchSuggestions();
            return;
        }

        try {
            const response = await this.makeApiCall('/search/suggestions', {
                queryParams: {
                    q: query,
                    limit: 10
                }
            });

            if (response.success && response.suggestions) {
                this.showSearchSuggestions(response.suggestions);
            }
        } catch (error) {
            console.error('Failed to get search suggestions:', error);
        }
    }

    async performSearch() {
        const query = this.elements.searchInput.value.trim();
        if (!query) {
            this.showError('Please enter a search query');
            return;
        }

        try {
            this.showLoading();
            
            const response = await this.makeApiCall('/search', {
                queryParams: {
                    q: query,
                    search_type: this.config.searchType,
                    limit: this.config.defaultPageSize
                }
            });

            if (response.success) {
                this.state.searchResults = response.results || [];
                this.renderSearchResults(response);
            } else {
                throw new Error(response.error || 'Search failed');
            }

        } catch (error) {
            console.error('Search failed:', error);
            this.showError('Search failed. Please try again.');
        } finally {
            this.hideLoading();
        }
    }

    renderSearchResults(response) {
        // Show search info
        if (this.elements.searchInfo) {
            this.elements.searchInfo.style.display = 'block';
            this.elements.searchInfoText.textContent = 
                `Found ${response.total_found} results in ${response.execution_time.toFixed(2)}s`;
        }

        // Show results
        if (this.elements.searchResultsList) {
            this.renderSearchResultsList(response.results || []);
        }
    }

    renderSearchResultsList(results) {
        if (!this.elements.searchResultsListContainer) return;

        this.elements.searchResultsListContainer.innerHTML = '';

        if (results.length === 0) {
            this.elements.searchResultsListContainer.innerHTML = `
                <div class="text-center text-muted py-4">
                    <i class="fas fa-search fa-3x mb-2"></i>
                    <p>No results found</p>
                </div>
            `;
            return;
        }

        results.forEach(result => {
            const item = this.createSearchResultItem(result);
            this.elements.searchResultsListContainer.appendChild(item);
        });
    }

    createSearchResultItem(result) {
        const div = document.createElement('div');
        div.className = 'list-group-item list-group-item-action search-result-item';
        
        const icon = this.getFileIcon(result.mime_type);
        const size = this.formatFileSize(result.file_size);

        div.innerHTML = `
            <div class="d-flex justify-content-between align-items-start">
                <div class="flex-grow-1">
                    <h6 class="mb-1">
                        <i class="${icon} me-2"></i>
                        <a href="#" class="text-decoration-none search-result-link" data-file-id="${result.file_id}">
                            ${result.file_name}
                        </a>
                    </h6>
                    <p class="mb-1 text-truncate">${result.excerpt || 'No excerpt available'}</p>
                    <small class="text-muted">
                        ${size} • Modified ${this.formatDate(result.modified_at)} • 
                        Score: ${(result.score || 0).toFixed(2)}
                    </small>
                </div>
                <div class="d-flex align-items-center">
                    <span class="badge bg-primary me-2">${result.file_type}</span>
                    <div class="btn-group btn-group-sm">
                        <button class="btn btn-outline-primary" data-action="open" data-file-id="${result.file_id}">
                            <i class="fas fa-external-link-alt"></i>
                        </button>
                        <button class="btn btn-outline-info" data-action="workflow" data-file-id="${result.file_id}">
                            <i class="fas fa-robot"></i>
                        </button>
                    </div>
                </div>
            </div>
        `;

        // Add event listeners
        const resultLink = div.querySelector('.search-result-link');
        if (resultLink) {
            resultLink.addEventListener('click', (e) => {
                e.preventDefault();
                this.openFile(result);
            });
        }

        const actionButtons = div.querySelectorAll('.btn');
        actionButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                const action = btn.dataset.action;
                this.handleSearchResultAction(action, result);
            });
        });

        return div;
    }

    // Automation
    async loadAutomationData() {
        try {
            const [workflowsResponse, executionsResponse] = await Promise.all([
                this.loadWorkflows(),
                this.loadExecutions()
            ]);

        } catch (error) {
            console.error('Failed to load automation data:', error);
        }
    }

    async loadWorkflows() {
        try {
            const response = await this.makeApiCall('/automation/workflows', {
                automationApi: true
            });

            if (response.success) {
                this.state.workflows = response.workflows || [];
                this.renderWorkflowsList();
            }
        } catch (error) {
            console.error('Failed to load workflows:', error);
        }
    }

    renderWorkflowsList() {
        if (!this.elements.workflowsTableBody) return;

        this.elements.workflowsTableBody.innerHTML = '';

        if (this.state.workflows.length === 0) {
            this.elements.workflowsTableBody.innerHTML = `
                <tr>
                    <td colspan="6" class="text-center text-muted">
                        <i class="fas fa-robot fa-3x mb-2"></i>
                        <p>No workflows created yet</p>
                        <button class="btn btn-primary" onclick="app.showWorkflowEditor()">
                            <i class="fas fa-plus me-2"></i>Create Your First Workflow
                        </button>
                    </td>
                </tr>
            `;
            return;
        }

        this.state.workflows.forEach(workflow => {
            const row = this.createWorkflowRow(workflow);
            this.elements.workflowsTableBody.appendChild(row);
        });
    }

    createWorkflowRow(workflow) {
        const tr = document.createElement('tr');
        tr.dataset.workflowId = workflow.id;

        const statusBadge = workflow.enabled ? 
            '<span class="badge bg-success">Enabled</span>' : 
            '<span class="badge bg-secondary">Disabled</span>';

        tr.innerHTML = `
            <td>
                <div class="d-flex align-items-center">
                    <i class="fas fa-robot me-2 text-primary"></i>
                    <div>
                        <strong>${workflow.name}</strong>
                        ${workflow.description ? `<br><small class="text-muted">${workflow.description}</small>` : ''}
                    </div>
                </div>
            </td>
            <td>${statusBadge}</td>
            <td>${workflow.triggers?.length || 0}</td>
            <td>${workflow.actions?.length || 0}</td>
            <td>${workflow.execution_stats?.last_execution?.status || 'Never'}</td>
            <td>
                ${workflow.execution_stats ? 
                    `${(workflow.execution_stats.success_rate || 0).toFixed(1)}%` : 
                    'N/A'
                }
            </td>
            <td>
                <div class="btn-group btn-group-sm">
                    <button class="btn btn-outline-primary" onclick="app.executeWorkflow('${workflow.id}')">
                        <i class="fas fa-play"></i>
                    </button>
                    <button class="btn btn-outline-info" onclick="app.editWorkflow('${workflow.id}')">
                        <i class="fas fa-edit"></i>
                    </button>
                    <button class="btn btn-outline-warning" onclick="app.cloneWorkflow('${workflow.id}')">
                        <i class="fas fa-copy"></i>
                    </button>
                    <button class="btn btn-outline-danger" onclick="app.deleteWorkflow('${workflow.id}')">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </td>
        `;

        return tr;
    }

    async executeWorkflow(workflowId) {
        try {
            const response = await this.makeApiCall(`/automation/workflows/${workflowId}/execute`, {
                automationApi: true,
                method: 'POST',
                body: JSON.stringify({
                    trigger_data: { manual_trigger: true }
                })
            });

            if (response.success) {
                this.showSuccess('Workflow execution started');
                await this.loadExecutions(); // Refresh executions
            } else {
                throw new Error(response.error || 'Failed to execute workflow');
            }
        } catch (error) {
            console.error('Failed to execute workflow:', error);
            this.showError('Failed to execute workflow');
        }
    }

    // Sync functionality
    async loadSyncData() {
        try {
            const [statsResponse, eventsResponse] = await Promise.all([
                this.loadSyncStats(),
                this.loadRecentEvents()
            ]);

        } catch (error) {
            console.error('Failed to load sync data:', error);
        }
    }

    async loadSyncStats() {
        try {
            const response = await this.makeApiCall('/automation/automation-stats', {
                automationApi: true
            });

            if (response.success) {
                this.updateSyncStats(response.stats);
            }
        } catch (error) {
            console.error('Failed to load sync stats:', error);
        }
    }

    updateSyncStats(stats) {
        if (this.elements.filesSyncedCount) {
            this.elements.filesSyncedCount.textContent = 
                stats.trigger_system?.processed_events || 0;
        }

        if (this.elements.embeddingsCount) {
            this.elements.embeddingsCount.textContent = 
                stats.action_system?.total_actions || 0; // Adjust as needed
        }

        if (this.elements.syncQueueCount) {
            this.elements.syncQueueCount.textContent = 
                stats.trigger_system?.pending_events || 0;
        }
    }

    async manualSync() {
        try {
            this.showLoading();
            
            // This would trigger a manual sync via the API
            const response = await this.makeApiCall('/sync/manual', {
                method: 'POST'
            });

            if (response.success) {
                this.showSuccess('Manual sync started');
                this.updateSyncStatus('syncing');
                await this.loadSyncData();
            } else {
                throw new Error(response.error || 'Failed to start sync');
            }

        } catch (error) {
            console.error('Manual sync failed:', error);
            this.showError('Failed to start manual sync');
        } finally {
            this.hideLoading();
        }
    }

    updateSyncStatus(status) {
        this.state.syncStatus = status;
        
        if (this.elements.syncIndicator) {
            const icon = this.elements.syncIndicator.querySelector('i');
            icon.className = status === 'syncing' ? 
                'fas fa-sync fa-spin fa-3x text-warning' : 
                'fas fa-sync fa-3x text-primary';
        }

        if (this.elements.syncStatusText) {
            this.elements.syncStatusText.textContent = 
                status === 'syncing' ? 'Syncing...' : 'Synced';
        }
    }

    // Live updates
    startLiveUpdates() {
        if (!this.config.liveUpdatesEnabled) return;

        // Initialize WebSocket or polling for live events
        this.eventSource = new EventSource(`${this.config.apiBaseUrl}/events/stream`);
        
        this.eventSource.addEventListener('message', (event) => {
            const data = JSON.parse(event.data);
            this.handleLiveEvent(data);
        });

        this.eventSource.addEventListener('error', () => {
            console.warn('Lost connection to event stream, attempting to reconnect...');
            setTimeout(() => this.startLiveUpdates(), 5000);
        });
    }

    stopLiveUpdates() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
    }

    handleLiveEvent(event) {
        this.state.liveEvents.unshift(event);
        
        // Keep only last 100 events
        if (this.state.liveEvents.length > 100) {
            this.state.liveEvents = this.state.liveEvents.slice(0, 100);
        }

        // Update UI if we're on the sync section
        if (this.config.currentSection === 'sync') {
            this.addLiveEventToUI(event);
        }
    }

    addLiveEventToUI(event) {
        if (!this.elements.liveEventsContainer) return;

        const eventElement = document.createElement('div');
        eventElement.className = 'alert alert-info mb-2';
        
        const icon = this.getEventIcon(event.event_type);
        const time = this.formatTime(event.timestamp);

        eventElement.innerHTML = `
            <div class="d-flex justify-content-between align-items-start">
                <div>
                    <i class="${icon} me-2"></i>
                    <strong>${event.event_type}</strong>
                    <div class="small text-muted">${event.resource_name || event.resource_id}</div>
                </div>
                <small>${time}</small>
            </div>
        `;

        // Add to top of container
        this.elements.liveEventsContainer.insertBefore(
            eventElement, 
            this.elements.liveEventsContainer.firstChild
        );

        // Remove old events
        while (this.elements.liveEventsContainer.children.length > 50) {
            this.elements.liveEventsContainer.removeChild(
                this.elements.liveEventsContainer.lastChild
            );
        }
    }

    // Utility functions
    getFileIcon(mimeType) {
        const iconMap = {
            'application/pdf': 'fas fa-file-pdf text-danger',
            'application/msword': 'fas fa-file-word text-primary',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'fas fa-file-word text-primary',
            'application/vnd.ms-excel': 'fas fa-file-excel text-success',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'fas fa-file-excel text-success',
            'application/vnd.ms-powerpoint': 'fas fa-file-powerpoint text-warning',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation': 'fas fa-file-powerpoint text-warning',
            'text/plain': 'fas fa-file-alt text-secondary',
            'image/jpeg': 'fas fa-file-image text-info',
            'image/png': 'fas fa-file-image text-info',
            'image/gif': 'fas fa-file-image text-info',
            'video/mp4': 'fas fa-file-video text-dark',
            'audio/mpeg': 'fas fa-file-audio text-secondary',
            'application/zip': 'fas fa-file-archive text-warning',
            'application/vnd.google-apps.folder': 'fas fa-folder text-warning',
            'application/vnd.google-apps.document': 'fas fa-file-alt text-primary',
            'application/vnd.google-apps.spreadsheet': 'fas fa-file-excel text-success',
            'application/vnd.google-apps.presentation': 'fas fa-file-powerpoint text-warning'
        };

        return iconMap[mimeType] || 'fas fa-file text-secondary';
    }

    getEventIcon(eventType) {
        const iconMap = {
            'file_created': 'fas fa-plus text-success',
            'file_updated': 'fas fa-edit text-warning',
            'file_deleted': 'fas fa-trash text-danger',
            'file_shared': 'fas fa-share text-info',
            'workflow_executed': 'fas fa-robot text-primary',
            'sync_completed': 'fas fa-sync text-success'
        };

        return iconMap[eventType] || 'fas fa-info-circle text-secondary';
    }

    formatFileSize(bytes) {
        if (!bytes || bytes === 0) return '-';
        
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(1024));
        
        return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${sizes[i]}`;
    }

    formatDate(dateString) {
        if (!dateString) return 'Never';
        
        const date = new Date(dateString);
        return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
    }

    formatTime(dateString) {
        if (!dateString) return 'Never';
        
        const date = new Date(dateString);
        return date.toLocaleTimeString();
    }

    // API helpers
    async makeApiCall(endpoint, options = {}) {
        const {
            method = 'GET',
            body = null,
            queryParams = {},
            automationApi = false
        } = options;

        try {
            const baseUrl = automationApi ? this.config.automationApiUrl : this.config.apiBaseUrl;
            const sessionId = this.getSessionId();
            
            let url = `${baseUrl}${endpoint}`;
            
            // Add query parameters
            if (Object.keys(queryParams).length > 0) {
                const params = new URLSearchParams(queryParams);
                url += `?${params.toString()}`;
            }

            const response = await fetch(url, {
                method,
                headers: {
                    'Content-Type': 'application/json',
                    'X-Session-ID': sessionId
                },
                body: body
            });

            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || `HTTP ${response.status}`);
            }

            return data;
            
        } catch (error) {
            console.error('API call failed:', error);
            throw error;
        }
    }

    // UI helpers
    showLoading() {
        if (this.elements.loadingOverlay) {
            this.elements.loadingOverlay.style.display = 'flex';
        }
    }

    hideLoading() {
        if (this.elements.loadingOverlay) {
            this.elements.loadingOverlay.style.display = 'none';
        }
    }

    showError(message) {
        this.showToast(message, 'danger');
    }

    showSuccess(message) {
        this.showToast(message, 'success');
    }

    showInfo(message) {
        this.showToast(message, 'info');
    }

    showToast(message, type = 'info') {
        if (!this.elements.toastContainer) return;

        const toastId = 'toast_' + Date.now();
        const toastHtml = `
            <div id="${toastId}" class="toast align-items-center text-white bg-${type} border-0" role="alert">
                <div class="d-flex">
                    <div class="toast-body">
                        ${message}
                    </div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
                </div>
            </div>
        `;

        this.elements.toastContainer.insertAdjacentHTML('beforeend', toastHtml);
        
        const toastElement = document.getElementById(toastId);
        const toast = new bootstrap.Toast(toastElement, {
            autohide: true,
            delay: 5000
        });
        
        toast.show();
        
        // Remove toast element after hidden
        toastElement.addEventListener('hidden.bs.toast', () => {
            toastElement.remove();
        });
    }

    // Keyboard shortcuts
    handleKeyboardShortcuts(e) {
        // Ctrl+K: Quick search
        if (e.ctrlKey && e.key === 'k') {
            e.preventDefault();
            this.switchSection('search');
            this.elements.searchInput?.focus();
        }
        
        // Ctrl+U: Upload file
        if (e.ctrlKey && e.key === 'u') {
            e.preventDefault();
            this.showFileUploadModal();
        }
        
        // Ctrl+N: New workflow
        if (e.ctrlKey && e.key === 'n') {
            e.preventDefault();
            this.showWorkflowEditor();
        }
        
        // Ctrl+R: Manual sync
        if (e.ctrlKey && e.key === 'r') {
            e.preventDefault();
            this.manualSync();
        }
    }

    // Initialize UI
    initializeUI() {
        // Initialize tooltips
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });

        // Initialize popovers
        const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
        popoverTriggerList.map(function (popoverTriggerEl) {
            return new bootstrap.Popover(popoverTriggerEl);
        });
    }

    // Placeholder methods for incomplete functionality
    async loadRecentActivity() {
        // Implementation for loading recent activity
        return [];
    }

    async loadExecutions() {
        // Implementation for loading executions
    }

    async loadRecentEvents() {
        // Implementation for loading recent events
    }

    async downloadFile(fileId, fileName) {
        // Implementation for downloading files
    }

    async shareFile(fileId) {
        // Implementation for sharing files
    }

    async processFile(fileId) {
        // Implementation for processing files
    }

    async openFile(file) {
        // Implementation for opening files
    }

    handleSearchResultAction(action, result) {
        // Implementation for handling search result actions
    }

    editWorkflow(workflowId) {
        // Implementation for editing workflows
    }

    cloneWorkflow(workflowId) {
        // Implementation for cloning workflows
    }

    deleteWorkflow(workflowId) {
        // Implementation for deleting workflows
    }

    initWorkflowEditor(workflow) {
        // Implementation for initializing workflow editor
    }

    toggleSelectAllFiles(checked) {
        // Implementation for selecting all files
    }

    updateBreadcrumb(folderId) {
        // Implementation for updating breadcrumb navigation
    }

    showSearchSuggestions(suggestions) {
        // Implementation for showing search suggestions
    }

    hideSearchSuggestions() {
        // Implementation for hiding search suggestions
    }
}

// Initialize application when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.app = new AtomGoogleDriveApp();
});

// Export for global access
window.AtomGoogleDriveApp = AtomGoogleDriveApp;