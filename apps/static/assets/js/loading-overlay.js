/**
 * Loading Overlay JavaScript
 * Provides functions to show and hide a loading overlay during processes
 */

const LoadingOverlay = {
  /**
   * Show the loading overlay with custom message
   * @param {string} message - Optional custom message to display
   */
  show: function(message = 'Mohon tunggu...') {
    // If overlay doesn't exist, create it
    if (!document.querySelector('.loading-overlay')) {
      const overlay = document.createElement('div');
      overlay.className = 'loading-overlay';
      
      const spinnerContainer = document.createElement('div');
      spinnerContainer.className = 'loading-spinner-container';
      
      const spinner = document.createElement('div');
      spinner.className = 'loading-spinner';
      
      const text = document.createElement('div');
      text.className = 'loading-text';
      text.id = 'loading-message';
      text.textContent = message;
      
      spinnerContainer.appendChild(spinner);
      spinnerContainer.appendChild(text);
      overlay.appendChild(spinnerContainer);
      
      document.body.appendChild(overlay);
    } else {
      // Update message if overlay exists
      document.getElementById('loading-message').textContent = message;
    }
    
    // Show overlay and prevent scrolling
    const overlay = document.querySelector('.loading-overlay');
    overlay.style.display = 'flex';
    document.body.classList.add('no-scroll');
  },
  
  /**
   * Hide the loading overlay
   */
  hide: function() {
    const overlay = document.querySelector('.loading-overlay');
    if (overlay) {
      overlay.style.display = 'none';
      document.body.classList.remove('no-scroll');
    }
  }
};

// Add event listeners for common form submissions
document.addEventListener('DOMContentLoaded', function() {
  // Show loading on form submissions
  document.querySelectorAll('form').forEach(form => {
    form.addEventListener('submit', function() {
      // Don't show loading for forms with data-no-loading attribute
      if (!this.hasAttribute('data-no-loading')) {
        LoadingOverlay.show('Memproses data...');
      }
    });
  });
  
  // Show loading on links with data-loading attribute
  document.querySelectorAll('a[data-loading="true"]').forEach(link => {
    link.addEventListener('click', function(e) {
      // Don't show loading if link has target="_blank"
      if (!this.getAttribute('target') || this.getAttribute('target') !== '_blank') {
        LoadingOverlay.show(this.getAttribute('data-loading-message') || 'Mohon tunggu...');
      }
    });
  });
  
  // Show loading on buttons with data-loading attribute
  document.querySelectorAll('button[data-loading="true"]').forEach(button => {
    button.addEventListener('click', function() {
      LoadingOverlay.show(this.getAttribute('data-loading-message') || 'Mohon tunggu...');
    });
  });
});

// Expose the LoadingOverlay object globally
window.LoadingOverlay = LoadingOverlay;