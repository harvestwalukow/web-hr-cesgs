/**
 * Attendance Notification System
 * Real-time browser notifications for overtime alerts (after 18:30)
 */

(function() {
    'use strict';

    // Configuration
    const OVERTIME_THRESHOLD_HOUR = 18;
    const OVERTIME_THRESHOLD_MINUTE = 30;
    const CHECK_INTERVAL = 60000; // Check every 1 minute
    
    let notificationShown = false;
    let checkInterval = null;

    /**
     * Request notification permission from user
     */
    function requestNotificationPermission() {
        if ('Notification' in window && Notification.permission === 'default') {
            Notification.requestPermission().then(permission => {
                console.log('Notification permission:', permission);
            });
        }
    }

    /**
     * Check if current time is past overtime threshold
     */
    function isPastOvertimeThreshold() {
        const now = new Date();
        const currentHour = now.getHours();
        const currentMinute = now.getMinutes();
        
        if (currentHour > OVERTIME_THRESHOLD_HOUR) {
            return true;
        } else if (currentHour === OVERTIME_THRESHOLD_HOUR && currentMinute >= OVERTIME_THRESHOLD_MINUTE) {
            return true;
        }
        return false;
    }

    /**
     * Show browser notification
     */
    function showOvertimeNotification() {
        if ('Notification' in window && Notification.permission === 'granted') {
            const notification = new Notification('⏰ Reminder Jam Pulang', {
                body: 'Sudah lewat jam 18:30! Anda dapat mengajukan klaim lembur untuk hari ini. Jangan lupa check-out.',
                icon: '/static/img/brand/favicon.png',
                badge: '/static/img/brand/favicon.png',
                tag: 'overtime-alert',
                requireInteraction: true,
                vibrate: [200, 100, 200]
            });

            notification.onclick = function() {
                window.focus();
                window.location.href = '/absensi/pulang/';
                notification.close();
            };

            console.log('Overtime notification shown');
        }
    }

    /**
     * Check overtime status via API
     */
    async function checkOvertimeStatus() {
        try {
            const response = await fetch('/absensi/api/check-overtime-status/');
            const data = await response.json();
            
            if (data.should_notify && !notificationShown) {
                showOvertimeNotification();
                notificationShown = true;
            }
            
            // Reset notification flag when new day starts or when checked out
            if (data.has_checked_out || !data.has_checked_in) {
                notificationShown = false;
            }
        } catch (error) {
            console.error('Error checking overtime status:', error);
        }
    }

    /**
     * Initialize the notification system
     */
    function initializeNotifications() {
        // Request permission on load
        requestNotificationPermission();
        
        // Check immediately if we're already past overtime
        if (isPastOvertimeThreshold()) {
            checkOvertimeStatus();
        }
        
        // Set up periodic checks
        checkInterval = setInterval(() => {
            if (isPastOvertimeThreshold()) {
                checkOvertimeStatus();
            }
        }, CHECK_INTERVAL);
        
        console.log('Attendance notification system initialized');
    }

    /**
     * Cleanup on page unload
     */
    function cleanup() {
        if (checkInterval) {
            clearInterval(checkInterval);
        }
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeNotifications);
    } else {
        initializeNotifications();
    }

    // Cleanup on page unload
    window.addEventListener('beforeunload', cleanup);

    // Expose API for manual control
    window.AttendanceNotifications = {
        requestPermission: requestNotificationPermission,
        checkStatus: checkOvertimeStatus,
        resetNotification: () => { notificationShown = false; }
    };
})();
