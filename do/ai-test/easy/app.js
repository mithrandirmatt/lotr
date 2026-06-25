// Splash Screen Configuration
const SPLASH_CONFIG = {
    // Stages of loading simulation
    stages: [
        { name: 'Connecting...', duration: 800 },
        { name: 'Initializing system', duration: 600 },
        { name: 'Loading resources', duration: 700 },
        { name: 'Preparing experience', duration: 500 }
    ],

    // Total time before showing hello world (in ms)
    totalTime: 3200,

    // Progress bar settings
    progressInterval: 100,

    // Status messages to show
    statusMessages: [
        { text: '✓ Connecting to system', delay: 850 },
        { text: '⏳ Loading resources...', delay: 1600 }
    ]
};

// DOM Elements
const splashScreen = document.getElementById('splash-screen');
const progressContainer = document.getElementById('progress-container');
const progressBar = document.querySelector('.progress-bar');
const progressFill = document.getElementById('progress-fill');
const progressText = document.getElementById('progress-text');
const statusMessagesDiv = document.getElementById('status-messages');

// State
let currentStage = 0;
let startTime = null;
let progressIntervalId = null;
let stageTimeouts = [];

/**
 * Initialize the splash screen experience
 */
function initSplashScreen() {
    console.log('🚀 Initializing splash screen...');

    // Start timing
    startTime = Date.now();

    // Show initial loader (no progress yet)
    setTimeout(() => {
        showInitialLoader();
    }, 300);

    // Schedule status messages
    SPLASH_CONFIG.statusMessages.forEach((msg, index) => {
        const timeoutId = setTimeout(() => {
            displayStatusMessage(msg.text);
        }, msg.delay);
        stageTimeouts.push(timeoutId);
    });

    // Start progress bar updates
    startProgressUpdates();

    // Schedule final transition to hello world
    scheduleFinalTransition();
}

/**
 * Show the initial loader without progress bar
 */
function showInitialLoader() {
    splashScreen.innerHTML = `
        <div class="splash-content">
            <div class="loader"></div>
            <h1>Loading...</h1>
            <p>Please wait while we prepare your experience</p>
        </div>

        <!-- Progress indicators -->
        <div id="progress-container" style="display: none;">
            <div class="progress-bar">
                <div id="progress-fill"></div>
            </div>
            <span id="progress-text">Initializing...</span>
        </div>

        <!-- Status messages -->
        <div id="status-messages" style="display: none; margin-top: 20px;">
            <p class="status-item">✓ Connecting to system</p>
            <p class="status-item status-loading">⏳ Loading resources...</p>
            <p class="status-item status-error"></p>
        </div>
    `;

    // Re-bind event listeners after innerHTML update
    const newProgressContainer = document.getElementById('progress-container');
    if (newProgressContainer) {
        newProgressContainer.addEventListener('click', handleProgressClick);
    }
}

/**
 * Start updating the progress bar
 */
function startProgressUpdates() {
    let lastUpdateTime = Date.now();

    // Update every 100ms for smooth animation
    progressIntervalId = setInterval(() => {
        const elapsed = Date.now() - startTime;
        updateProgressBar(elapsed);

        // Check if we should show the full status messages
        checkStatusMessagesVisibility(elapsed);
    }, SPLASH_CONFIG.progressInterval);
}

/**
 * Update the progress bar based on elapsed time
 */
function updateProgressBar(elapsed) {
    const total = SPLASH_CONFIG.totalTime;
    let percentage = (elapsed / total) * 100;

    // Clamp between 0 and 100
    if (percentage < 0) percentage = 0;
    if (percentage > 100) {
        showHelloWorld();
        return;
    }

    progressFill.style.width = `${Math.min(percentage, 100)}%`;
}

/**
 * Check when to show the full status messages section
 */
function checkStatusMessagesVisibility(elapsed) {
    const messageDelay = SPLASH_CONFIG.statusMessages[SPLASH_CONFIG.statusMessages.length - 1].delay;

    if (elapsed > messageDelay && !statusMessagesDiv.style.display) {
        // Show progress container first
        new Promise(resolve => setTimeout(resolve, 200)).then(() => {
            showProgressContainer();

            // Then show status messages after a short delay
            setTimeout(showStatusMessages, 300);
        });
    }
}

/**
 * Show the progress bar container
 */
function showProgressContainer() {
    const container = document.getElementById('progress-container');
    if (container) {
        container.style.display = 'block';

        // Add click handler for interactive effect
        container.addEventListener('click', handleProgressClick);
    }
}

/**
 * Show the status messages section
 */
function showStatusMessages() {
    const div = document.getElementById('status-messages');
    if (div) {
        div.style.display = 'block';

        // Update loading message to spinning icon
        setTimeout(() => {
            const loadingMsg = div.querySelector('.status-loading');
            if (loadingMsg && !loadingMsg.classList.contains('check')) {
                loadingMsg.className = 'status-item status-loading';
                loadingMsg.innerHTML = '<span class="spinner"></span> Loading resources...';

                // Add spinner animation
                const spinner = document.createElement('div');
                spinner.className = 'spinner';
                spinner.style.cssText = `
                    display: inline-block;
                    width: 12px;
                    height: 12px;
                    border: 2px solid rgba(255,255,255,0.3);
                    border-top-color: white;
                    border-radius: 50%;
                    animation: spin 0.8s linear infinite;
                `;
                loadingMsg.insertBefore(spinner, loadingMsg.firstChild);
            }
        }, 1000);
    }
}

/**
 * Handle click on progress bar (interactive effect)
 */
function handleProgressClick() {
    const fill = document.getElementById('progress-fill');
    if (!fill) return;

    // Add a quick pulse animation on each click
    fill.style.transform = 'scale(1.05)';
    setTimeout(() => {
        fill.style.transform = '';
    }, 100);
}

/**
 * Display status messages one by one
 */
function displayStatusMessage(text) {
    const div = document.getElementById('status-messages');
    if (!div) return;

    // Remove loading spinner from previous message
    const existingLoading = div.querySelector('.status-loading:not(.check)');
    if (existingLoading) {
        existingLoading.className = 'status-item check';
        existingLoading.innerHTML = text.replace('⏳', '✓');
    } else {
        // Create new status item
        const newItem = document.createElement('p');
        newItem.className = 'status-item check';
        newItem.textContent = text;

        if (div.firstChild) {
            div.insertBefore(newItem, div.firstChild);
        } else {
            div.appendChild(newItem);
        }
    }
}

/**
 * Schedule the transition to hello world screen
 */
function scheduleFinalTransition() {
    setTimeout(() => {
        showHelloWorld();
    }, SPLASH_CONFIG.totalTime + 200); // Extra time for fade-out animation
}

/**
 * Show the final hello world screen
 */
function showHelloWorld() {
    console.log('✨ Showing Hello World!');

    // Hide splash screen with fade effect
    if (splashScreen) {
        splashScreen.classList.add('fade-out');

        setTimeout(() => {
            // Remove from DOM after animation completes
            if (splashScreen.parentNode) {
                splashScreen.parentNode.removeChild(splashScreen);
            }

            // Show hello world screen
            showHelloWorldContent();
        }, 800);
    } else {
        // If splash already gone, just show hello world directly
        showHelloWorldContent();
    }
}

/**
 * Create and display the hello world content
 */
function showHelloWorldContent() {
    const helloScreen = document.getElementById('hello-screen');

    if (!helloScreen) {
        // Create hello screen from scratch
        const container = document.createElement('div');
        container.id = 'hello-screen';

        container.innerHTML = `
            <div class="hello-content">
                <h1>Hello, World!</h1>
                <p>Welcome to the Easy Tier Project</p>
                <p>This splash screen successfully transitioned to this final page.</p>
            </div>
        `;

        document.body.appendChild(container);
    } else {
        // Update existing hello screen content
        const content = container.querySelector('.hello-content');
        if (content) {
            content.innerHTML = `
                <h1>Hello, World!</h1>
                <p>Welcome to the Easy Tier Project</p>
                <p>This splash screen successfully transitioned to this final page.</p>
            `;
        }
    }

    // Add some confetti effect for celebration!
    setTimeout(addConfetti, 500);
}

/**
 * Simple confetti effect for the hello world moment
 */
function addConfetti() {
    const colors = ['#ff6b6b', '#feca57', '#48dbfb', '#ff9ff3', '#54a0ff'];

    for (let i = 0; i < 100; i++) {
        setTimeout(() => {
            createConfettiPiece(colors[Math.floor(Math.random() * colors.length)]);
        }, Math.random() * 2000);
    }
}

function createConfettiPiece(color) {
    const confetti = document.createElement('div');
    confetti.style.cssText = `
        position: fixed;
        left: ${Math.random() * 100}vw;
        top: -10px;
        width: 8px;
        height: 8px;
        background: ${color};
        border-radius: ${Math.random() > 0.5 ? '50%' : '2px'};
        animation: confetti-fall ${3 + Math.random() * 2}s linear forwards;
        z-index: 9998;
    `;

    document.body.appendChild(confetti);

    // Remove after animation completes
    setTimeout(() => {
        if (confetti.parentNode) {
            confetti.parentNode.removeChild(confetti);
        }
    }, 5000);
}

// Add keyframes for confetti falling
if (!document.querySelector('#confetti-keyframes')) {
    const style = document.createElement('style');
    style.id = 'confetti-keyframes';
    style.textContent = `
@keyframes confetti-fall {
    0% { transform: translateY(0) rotate(0deg); opacity: 1; }
    100% { transform: translateY(100vh) rotate(720deg); opacity: 0; }
}
`;
    document.head.appendChild(style);
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initSplashScreen);
} else {
    // Already loaded, initialize immediately
    initSplashScreen();
}
