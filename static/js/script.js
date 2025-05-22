document.addEventListener('DOMContentLoaded', () => {
    // DOM elements
    const researchForm = document.getElementById('researchForm');
    const loadingIndicator = document.getElementById('loadingIndicator');
    const resultsContainer = document.getElementById('resultsContainer');
    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');
    const submitBtn = document.getElementById('submitBtn');
    const submitText = document.getElementById('submitText');
    const loadingText = document.getElementById('loadingText');
    const newSearchBtn = document.getElementById('newSearchBtn');
    
    // Progress ring animation
    function setProgress(percent) {
        const circle = document.querySelector('.progress-ring-circle');
        const radius = circle.r.baseVal.value;
        const circumference = radius * 2 * Math.PI;
        const offset = circumference - (percent / 100) * circumference;
        circle.style.strokeDashoffset = offset;
    }
    
    // Animate progress during loading
    let progressInterval;
    function startProgressAnimation() {
        let progress = 0;
        progressInterval = setInterval(() => {
            progress += Math.random() * 15;
            if (progress > 90) progress = 90;
            setProgress(progress);
        }, 500);
    }
    
    function stopProgressAnimation() {
        clearInterval(progressInterval);
        setProgress(100);
    }
    
    // Handle tab switching with smooth animations
    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            // Remove active class from all buttons and contents
            tabButtons.forEach(btn => {
                btn.classList.remove('active');
                btn.classList.add('text-gray-500');
                btn.classList.remove('text-gray-700');
            });
            tabContents.forEach(content => {
                content.classList.remove('active');
                content.classList.add('hidden');
            });
            
            // Add active class to current button and content
            button.classList.add('active');
            button.classList.remove('text-gray-500');
            button.classList.add('text-gray-700');
            
            const tabId = button.getAttribute('data-tab');
            const activeContent = document.getElementById(tabId);
            activeContent.classList.remove('hidden');
            activeContent.classList.add('active');
            
            // Add animation
            activeContent.style.opacity = '0';
            activeContent.style.transform = 'translateY(10px)';
            setTimeout(() => {
                activeContent.style.transition = 'all 0.3s ease';
                activeContent.style.opacity = '1';
                activeContent.style.transform = 'translateY(0)';
            }, 10);
        });
    });
    
    // Handle new search button
    newSearchBtn.addEventListener('click', () => {
        resultsContainer.classList.add('hidden');
        document.getElementById('companyName').value = '';
        document.getElementById('jobRole').value = '';
        document.getElementById('companyName').focus();
        
        // Smooth scroll to form
        document.querySelector('form').scrollIntoView({
            behavior: 'smooth',
            block: 'center'
        });
    });
    
    // Handle form submission
    researchForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        // Get form values and validate
        const companyName = document.getElementById('companyName').value.trim();
        const jobRole = document.getElementById('jobRole').value.trim();
        
        if (!companyName) {
            showNotification('Please enter a company name', 'error');
            return;
        }
        
        // Update UI for loading state
        submitText.classList.add('hidden');
        loadingText.classList.remove('hidden');
        submitBtn.disabled = true;
        submitBtn.classList.add('opacity-75', 'cursor-not-allowed');
        
        // Show loading indicator with animation
        loadingIndicator.classList.remove('hidden');
        resultsContainer.classList.add('hidden');
        startProgressAnimation();
        
        // Smooth scroll to loading indicator
        setTimeout(() => {
            loadingIndicator.scrollIntoView({
                behavior: 'smooth',
                block: 'center'
            });
        }, 100);
        
        try {
            const startTime = Date.now();
            
            // Make API request
            const response = await fetch('/research', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    company_name: companyName,
                    job_role: jobRole || null
                }),
            });
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `Server error: ${response.status}`);
            }
            
            const data = await response.json();
            const processingTime = ((Date.now() - startTime) / 1000).toFixed(1);
            
            // Stop progress animation
            stopProgressAnimation();
            
            // Populate results
            populateResults(data, processingTime);
            
            // Hide loading, show results with animation
            setTimeout(() => {
                loadingIndicator.classList.add('hidden');
                resultsContainer.classList.remove('hidden');
                
                // Scroll to results
                setTimeout(() => {
                    resultsContainer.scrollIntoView({
                        behavior: 'smooth',
                        block: 'start'
                    });
                }, 100);
                
                showNotification('Research completed successfully!', 'success');
            }, 1000);
            
        } catch (error) {
            console.error('Error:', error);
            stopProgressAnimation();
            loadingIndicator.classList.add('hidden');
            showNotification(`Research failed: ${error.message}`, 'error');
        } finally {
            // Reset button state
            submitText.classList.remove('hidden');
            loadingText.classList.add('hidden');
            submitBtn.disabled = false;
            submitBtn.classList.remove('opacity-75', 'cursor-not-allowed');
        }
    });
    
    // Show notification function
    function showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `fixed top-4 right-4 z-50 px-6 py-4 rounded-lg shadow-lg text-white font-medium transform translate-x-full transition-transform duration-300 ${
            type === 'success' ? 'bg-green-500' : 
            type === 'error' ? 'bg-red-500' : 'bg-blue-500'
        }`;
        
        notification.innerHTML = `
            <div class="flex items-center">
                <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'} mr-2"></i>
                ${message}
            </div>
        `;
        
        document.body.appendChild(notification);
        
        // Animate in
        setTimeout(() => {
            notification.style.transform = 'translateX(0)';
        }, 100);
        
        // Animate out and remove
        setTimeout(() => {
            notification.style.transform = 'translateX(full)';
            setTimeout(() => {
                document.body.removeChild(notification);
            }, 300);
        }, 4000);
    }
    
    // Populate results function
    function populateResults(data, processingTime) {
        // Company title and info
        document.getElementById('companyTitle').textContent = data.company_name;
        document.getElementById('processTime').textContent = processingTime;
        
        const jobRoleInfo = document.getElementById('jobRoleInfo');
        jobRoleInfo.textContent = data.job_role ? 
            `Research tailored for ${data.job_role} position` : 
            'General company research';
        
        // AI Summary with improved formatting
        const aiSummary = document.getElementById('aiSummary');
        aiSummary.innerHTML = formatContent(data.ai_summary);
        
        // Company Overview
        document.getElementById('companySummary').textContent = 
            data.company_info.summary || 'Company summary not available.';
        
        const companyDetails = document.getElementById('companyDetails');
        companyDetails.innerHTML = '';
        
        if (data.company_info.details && Object.keys(data.company_info.details).length > 0) {
            Object.entries(data.company_info.details).forEach(([key, value]) => {
                const detailItem = document.createElement('div');
                detailItem.className = 'flex items-start p-3 bg-gray-50 rounded-lg';
                detailItem.innerHTML = `
                    <div class="flex-shrink-0 w-2 h-2 bg-blue-500 rounded-full mt-2 mr-3"></div>
                    <div>
                        <span class="font-semibold text-gray-800">${key}:</span>
                        <span class="text-gray-700 ml-2">${value}</span>
                    </div>
                `;
                companyDetails.appendChild(detailItem);
            });
        } else {
            companyDetails.innerHTML = `
                <div class="col-span-2 text-center py-8 text-gray-500">
                    <i class="fas fa-info-circle text-2xl mb-2"></i>
                    <p>Detailed company information is being gathered...</p>
                </div>
            `;
        }
        
        // Recent News
        const companyNews = document.getElementById('companyNews');
        companyNews.innerHTML = '';
        
        if (data.news.articles && data.news.articles.length > 0) {
            data.news.articles.forEach((article, index) => {
                const newsItem = document.createElement('div');
                newsItem.className = 'bg-white border border-gray-200 rounded-xl p-6 hover:shadow-lg transition-shadow duration-300';
                
                const isValidUrl = article.url && article.url !== '#';
                
                newsItem.innerHTML = `
                    <div class="flex items-start">
                        <div class="flex-shrink-0 w-12 h-12 bg-gradient-to-r from-green-400 to-blue-500 rounded-lg flex items-center justify-center mr-4">
                            <i class="fas fa-newspaper text-white"></i>
                        </div>
                        <div class="flex-grow">
                            <h4 class="font-bold text-lg text-gray-800 mb-2">
                                ${isValidUrl ? 
                                    `<a href="${article.url}" target="_blank" class="hover:text-blue-600 transition-colors duration-200">${article.title}</a>` : 
                                    article.title
                                }
                            </h4>
                            <p class="text-gray-600 mb-3 leading-relaxed">${article.description}</p>
                            <div class="flex items-center justify-between text-sm text-gray-500">
                                <div class="flex items-center">
                                    <i class="fas fa-calendar-alt mr-1"></i>
                                    ${formatDate(article.publishedAt)}
                                </div>
                                ${article.source ? `
                                    <div class="flex items-center">
                                        <i class="fas fa-building mr-1"></i>
                                        ${article.source}
                                    </div>
                                ` : ''}
                            </div>
                        </div>
                    </div>
                `;
                
                companyNews.appendChild(newsItem);
            });
        } else {
            companyNews.innerHTML = `
                <div class="text-center py-12 text-gray-500">
                    <i class="fas fa-newspaper text-4xl mb-4"></i>
                    <p class="text-lg">No recent news available at this time</p>
                    <p class="text-sm mt-2">We'll continue monitoring for updates</p>
                </div>
            `;
        }
        
        // Employee Reviews
        const employeeReviews = document.getElementById('employeeReviews');
        employeeReviews.innerHTML = '';
        
        if (data.reviews && data.reviews.length > 0) {
            data.reviews.forEach((review, index) => {
                const rating = parseFloat(review.rating);
                const fullStars = Math.floor(rating);
                const hasHalfStar = rating % 1 >= 0.5;
                
                const reviewItem = document.createElement('div');
                reviewItem.className = `bg-white border-l-4 ${getRatingBorderColor(rating)} rounded-lg p-6 shadow-sm hover:shadow-md transition-shadow duration-300`;
                
                reviewItem.innerHTML = `
                    <div class="flex items-start justify-between mb-4">
                        <div>
                            <h4 class="font-bold text-lg text-gray-800 mb-1">${review.title}</h4>
                            <div class="flex items-center mb-2">
                                <div class="flex items-center rating-stars mr-3">
                                    ${generateStarRating(rating)}
                                </div>
                                <span class="text-sm font-semibold text-gray-600">${rating}/5.0</span>
                            </div>
                            ${review.role ? `<p class="text-sm text-gray-500 mb-2">${review.role}</p>` : ''}
                            ${review.date ? `<p class="text-xs text-gray-400">${formatDate(review.date)}</p>` : ''}
                        </div>
                        <div class="flex-shrink-0 w-12 h-12 ${getRatingBgColor(rating)} rounded-lg flex items-center justify-center">
                            <i class="fas fa-user text-white"></i>
                        </div>
                    </div>
                    
                    <div class="space-y-3">
                        <div class="bg-green-50 border-l-4 border-green-400 p-3 rounded">
                            <p class="text-sm font-semibold text-green-800 mb-1">
                                <i class="fas fa-thumbs-up mr-1"></i>Pros:
                            </p>
                            <p class="text-sm text-green-700">${review.pros}</p>
                        </div>
                        
                        <div class="bg-red-50 border-l-4 border-red-400 p-3 rounded">
                            <p class="text-sm font-semibold text-red-800 mb-1">
                                <i class="fas fa-thumbs-down mr-1"></i>Cons:
                            </p>
                            <p class="text-sm text-red-700">${review.cons}</p>
                        </div>
                    </div>
                `;
                
                employeeReviews.appendChild(reviewItem);
            });
        } else {
            employeeReviews.innerHTML = `
                <div class="text-center py-12 text-gray-500">
                    <i class="fas fa-users text-4xl mb-4"></i>
                    <p class="text-lg">No employee reviews available</p>
                    <p class="text-sm mt-2">Employee feedback will be displayed here when available</p>
                </div>
            `;
        }
    }
    
    // Helper functions
    function formatContent(text) {
        if (!text) return '<p class="text-gray-500">Content not available</p>';
        
        // Enhanced markdown-style formatting
        let formatted = text
            // Headers
            .replace(/^### (.*$)/gim, '<h3 class="text-xl font-bold text-gray-800 mt-6 mb-3">$1</h3>')
            .replace(/^## (.*$)/gim, '<h2 class="text-2xl font-bold text-gray-800 mt-8 mb-4">$1</h2>')
            .replace(/^# (.*$)/gim, '<h1 class="text-3xl font-bold text-gray-800 mt-8 mb-4">$1</h1>')
            
            // Bold and italic
            .replace(/\*\*(.*?)\*\*/g, '<strong class="font-semibold text-gray-800">$1</strong>')
            .replace(/\*(.*?)\*/g, '<em class="italic">$1</em>')
            
            // Lists
            .replace(/^\* (.*$)/gim, '<li class="mb-2">$1</li>')
            .replace(/^- (.*$)/gim, '<li class="mb-2">$1</li>')
            .replace(/^(\d+)\. (.*$)/gim, '<li class="mb-2">$1. $2</li>');
        
        // Wrap consecutive list items in ul tags
        formatted = formatted.replace(/(<li class="mb-2">.*?<\/li>\s*)+/gs, function(match) {
            return '<ul class="list-disc list-inside space-y-2 mb-4 ml-4 text-gray-700">' + match + '</ul>';
        });
        
        // Convert paragraphs
        const lines = formatted.split('\n');
        const paragraphs = [];
        let currentParagraph = '';
        
        for (let line of lines) {
            line = line.trim();
            if (line === '') {
                if (currentParagraph) {
                    paragraphs.push(currentParagraph);
                    currentParagraph = '';
                }
            } else if (!line.match(/^<[h1-6ul]/)) {
                if (currentParagraph) currentParagraph += ' ';
                currentParagraph += line;
            } else {
                if (currentParagraph) {
                    paragraphs.push(currentParagraph);
                    currentParagraph = '';
                }
                paragraphs.push(line);
            }
        }
        
        if (currentParagraph) {
            paragraphs.push(currentParagraph);
        }
        
        // Wrap non-HTML content in paragraph tags
        return paragraphs.map(p => {
            if (p.match(/^<[h1-6ul]/)) {
                return p;
            } else {
                return `<p class="mb-4 text-gray-700 leading-relaxed">${p}</p>`;
            }
        }).join('');
    }
    
    function formatDate(dateString) {
        if (!dateString) return 'Unknown date';
        try {
            const date = new Date(dateString);
            return date.toLocaleDateString('en-US', { 
                year: 'numeric', 
                month: 'long', 
                day: 'numeric' 
            });
        } catch {
            return dateString;
        }
    }
    
    function generateStarRating(rating) {
        const fullStars = Math.floor(rating);
        const hasHalfStar = rating % 1 >= 0.5;
        const emptyStars = 5 - fullStars - (hasHalfStar ? 1 : 0);
        
        let stars = '';
        
        // Full stars
        for (let i = 0; i < fullStars; i++) {
            stars += '<i class="fas fa-star"></i>';
        }
        
        // Half star
        if (hasHalfStar) {
            stars += '<i class="fas fa-star-half-alt"></i>';
        }
        
        // Empty stars
        for (let i = 0; i < emptyStars; i++) {
            stars += '<i class="far fa-star"></i>';
        }
        
        return stars;
    }
    
    function getRatingBorderColor(rating) {
        if (rating >= 4.5) return 'border-green-500';
        if (rating >= 4.0) return 'border-blue-500';
        if (rating >= 3.5) return 'border-yellow-500';
        if (rating >= 3.0) return 'border-orange-500';
        return 'border-red-500';
    }
    
    function getRatingBgColor(rating) {
        if (rating >= 4.5) return 'bg-green-500';
        if (rating >= 4.0) return 'bg-blue-500';
        if (rating >= 3.5) return 'bg-yellow-500';
        if (rating >= 3.0) return 'bg-orange-500';
        return 'bg-red-500';
    }
    
    // Initialize progress ring
    setProgress(0);
    
    // Add keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        if (e.ctrlKey || e.metaKey) {
            switch(e.key) {
                case 'Enter':
                    if (document.activeElement.tagName !== 'BUTTON') {
                        e.preventDefault();
                        researchForm.dispatchEvent(new Event('submit'));
                    }
                    break;
                case 'n':
                    if (!resultsContainer.classList.contains('hidden')) {
                        e.preventDefault();
                        newSearchBtn.click();
                    }
                    break;
            }
        }
    });
    
    // Auto-focus on company name input
    document.getElementById('companyName').focus();
});