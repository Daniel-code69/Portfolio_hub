document.addEventListener('DOMContentLoaded', () => {

    const loggedInUserId = document.body.dataset.userId;

    // --- ELEMENT SELECTORS ---
    const portfolioForm = document.getElementById('portfolioForm');
    const portfolioGrid = document.getElementById('portfolioGrid');
    const messageContainer = document.getElementById('messageContainer');
    const filterButtons = document.querySelectorAll('.filter-btn');
    const fileInput = document.getElementById('files');
    const fileListPreview = document.getElementById('fileListPreview');
    const searchForm = document.getElementById('searchForm');

    // --- UTILITY FUNCTIONS ---
    const sanitizeHTML = (str) => {
        const temp = document.createElement('div');
        temp.textContent = str;
        return temp.innerHTML;
    };

    const showMessage = (message, type = 'error') => {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}`;
        messageDiv.textContent = message;
        const mainMessageContainer = document.querySelector('#messageContainer');
        mainMessageContainer.appendChild(messageDiv);
        setTimeout(() => {
            messageDiv.style.opacity = '0';
            messageDiv.addEventListener('transitionend', () => messageDiv.remove());
        }, 5000);
    };

    const toggleLoadingState = (isLoading) => {
        if (isLoading) {
            portfolioGrid.innerHTML = `<div class="loader">Loading portfolios...</div>`;
        } else {
            const loader = portfolioGrid.querySelector('.loader');
            if (loader) loader.remove();
        }
    };

    // --- PORTFOLIO RENDERING ---
    const createPortfolioItem = (portfolio) => {
        const item = document.createElement('div');
        item.className = 'portfolio-item card-3d hidden';
        item.dataset.id = portfolio.id;
        item.dataset.category = portfolio.category;

        const createSection = (title, content) => {
            if (!content || content.trim() === '') return '';
            return `
                <div class="portfolio-section">
                    <h4>${title}</h4>
                    <p>${sanitizeHTML(content).replace(/\n/g, '<br>')}</p> 
                </div>`;
        };

        const fileLinks = (portfolio.files || []).map(file => `<a href="/download/${portfolio.id}/${encodeURIComponent(file)}" class="file-link">${sanitizeHTML(file)}</a>`).join('');
        const projectLink = portfolio.project_url ? `<a href="${encodeURI(portfolio.project_url)}" target="_blank" rel="noopener noreferrer" class="project-link">View Live Project</a>` : '';
        
        let ownerActions = '';
        if (loggedInUserId && parseInt(loggedInUserId) === portfolio.user_id) {
            ownerActions = `<div class="owner-actions"><a href="/portfolio/${portfolio.id}/edit" class="btn-edit">Edit</a><button class="btn-delete" data-id="${portfolio.id}">Delete</button></div>`;
        }

        const studentNameHTML = `<a href="/profile/${sanitizeHTML(portfolio.owner_username)}" class="student-name-link">${sanitizeHTML(portfolio.owner_username)}</a>`;
        const likedClass = portfolio.is_liked ? 'liked' : '';
        const likeButtonHTML = `<div class="like-section"><button class="like-btn ${likedClass}" data-id="${portfolio.id}">👍</button><span class="like-count">${portfolio.like_count}</span></div>`;

        item.innerHTML = `
            ${ownerActions}
            <h3>${sanitizeHTML(portfolio.portfolio_title)}</h3>
            <p class="student-name">By: ${studentNameHTML}</p>
            <hr class="card-divider">
            
            ${createSection('About Me', portfolio.description)}
            ${createSection('Project Description', portfolio.project_description)}
            ${createSection('Skills', portfolio.skills)}
            ${createSection('Featured Projects', portfolio.projects)}
            
            <div class="portfolio-meta">
                <span class="category">${sanitizeHTML(portfolio.category)}</span>
                <span class="upload-date">${new Date(portfolio.upload_date).toLocaleDateString()}</span>
            </div>
            
            <div class="card-actions">
                <div>${projectLink}<div class="file-list">${fileLinks}</div></div>
                ${likeButtonHTML}
            </div>`;
        return item;
    };

    const loadPortfolios = async (searchQuery = '') => {
        // ... (code remains the same)
        if (!portfolioGrid) return;
        toggleLoadingState(true);
        try {
            const response = await fetch(`/portfolios?query=${encodeURIComponent(searchQuery)}`);
            if (!response.ok) throw new Error('Failed to fetch portfolios.');
            const portfolios = await response.json();
            toggleLoadingState(false);
            portfolioGrid.innerHTML = '';
            if (portfolios.length === 0) {
                portfolioGrid.innerHTML = `<p class="empty-gallery-message">No portfolios found. Try a different search.</p>`;
                return;
            }
            portfolios.forEach((portfolio, index) => {
                const item = createPortfolioItem(portfolio);
                portfolioGrid.appendChild(item);
                setTimeout(() => {
                    item.classList.remove('hidden');
                }, 100 * index);
            });
        } catch (error) {
            toggleLoadingState(false);
            portfolioGrid.innerHTML = `<p class="error-message">Could not load portfolios.</p>`;
            console.error('Failed to load portfolios:', error);
        }
    };

    // --- EVENT LISTENERS ---
    if (searchForm) {
        // ... (code remains the same)
        searchForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const searchInput = document.getElementById('searchInput');
            loadPortfolios(searchInput.value);
        });
    }

    if (portfolioForm) {
        // ... (code remains the same)
        portfolioForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const submitBtn = portfolioForm.querySelector('.submit-btn');
            const formData = new FormData(portfolioForm);
            submitBtn.textContent = 'Uploading...';
            submitBtn.disabled = true;
            try {
                const response = await fetch('/upload', { method: 'POST', body: formData, headers: { 'X-Requested-With': 'XMLHttpRequest' } });
                if (!response.ok) {
                    if (response.status === 401 || response.status === 403) { throw new Error('Your session has expired. Please log in again.'); }
                    throw new Error('An unknown error occurred during upload.');
                }
                const result = await response.json();
                showMessage(result.message, 'success');
                portfolioForm.reset();
                if(fileListPreview) fileListPreview.innerHTML = '';
                loadPortfolios();
            } catch (error) {
                showMessage(error.message, 'error');
                if (error.message.includes('session has expired')) {
                    setTimeout(() => { window.location.href = '/login'; }, 2000);
                }
            } finally {
                submitBtn.textContent = 'Upload Portfolio';
                submitBtn.disabled = false;
            }
        });
    }

    if(portfolioGrid) {
        // ... (code remains the same)
        portfolioGrid.addEventListener('click', async (e) => {
            if (e.target.classList.contains('btn-delete')) {
                const portfolioId = e.target.dataset.id;
                if (confirm('Are you sure you want to delete this portfolio? This cannot be undone.')) {
                    try {
                        const response = await fetch(`/portfolio/${portfolioId}/delete`, { method: 'POST' });
                        const result = await response.json();
                        if(response.ok) {
                            showMessage(result.message, 'success');
                            e.target.closest('.portfolio-item').remove();
                        } else { throw new Error(result.message); }
                    } catch (error) { showMessage(error.message, 'error'); }
                }
            }
            if (e.target.classList.contains('like-btn')) {
                if (!loggedInUserId) {
                    showMessage('You must be logged in to like a portfolio.', 'error');
                    return;
                }
                const portfolioId = e.target.dataset.id;
                const likeButton = e.target;
                const likeCountSpan = likeButton.nextElementSibling;
                try {
                    const response = await fetch(`/portfolio/${portfolioId}/like`, { method: 'POST', headers: { 'X-Requested-With': 'XMLHttpRequest' } });
                    const result = await response.json();
                    if (response.ok) {
                        likeCountSpan.textContent = result.like_count;
                        likeButton.classList.toggle('liked', result.liked);
                    } else { throw new Error('Failed to update like status.'); }
                } catch (error) { showMessage(error.message, 'error'); }
            }
        });
    }

    if(filterButtons) {
        // ... (code remains the same)
        filterButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                filterButtons.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                const filter = btn.dataset.filter;
                document.querySelectorAll('.portfolio-item').forEach(item => {
                    item.style.display = (filter === 'all' || item.dataset.category === filter) ? 'block' : 'none';
                });
            });
        });
    }

    if (fileInput) {
        // ... (code remains the same)
        fileInput.addEventListener('change', () => {
            if (fileInput.files.length > 0) { fileListPreview.textContent = `${fileInput.files.length} file(s) selected`; } 
            else { fileListPreview.textContent = ''; }
        });
    }

    if(portfolioGrid) { loadPortfolios(); }
});