/**
 * Live2D Widget for Ninta HP
 * Using pixi-live2d-display@0.4.0 with Cubism 4
 * Displays Ninta icon and switchable models
 */

(function() {
  'use strict';

  // Available models with obfuscated paths
  const models = {
    'ninta': {
      path: '/static/live2d/Ninta2DCo_VTuber/Ninta2DCo_VTuber.model3.json',
      name: 'Ninta2DCo',
      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
    },
    'michelle': {
      path: '/static/live2d/VTuber_Michelle/VTuber_Michelle.model3.json',
      name: 'VTuber Michelle',
      background: '#ddd'
    },
    'amamizu': {
      path: '/static/live2d/AmamizuAi_VTuber/AmamizuAi_VTuber.model3.json',
      name: 'Amamizu Ai',
      background: 'linear-gradient(135deg, #67b7ea 0%, #4776ba 100%)'
    }
  };

  // Add watermark to Live2D widget
  function addWatermark() {
    const widget = document.getElementById('live2d-widget');
    if (!widget) return;

    // Remove existing watermarks if any
    const existingWatermarks = widget.querySelectorAll('.live2d-watermark, .live2d-watermark-overlay');
    existingWatermarks.forEach(el => el.remove());

    // Add corner watermark
    const watermark = document.createElement('div');
    watermark.className = 'live2d-watermark';
    watermark.textContent = '© Ninta - Sample';
    widget.appendChild(watermark);

    // Add diagonal overlay watermark
    const overlay = document.createElement('div');
    overlay.className = 'live2d-watermark-overlay';
    overlay.textContent = '© Ninta 2024 - SAMPLE';
    widget.appendChild(overlay);
  }

  // Disable right-click on Live2D widget
  document.addEventListener('DOMContentLoaded', function() {
    const widget = document.getElementById('live2d-widget');
    if (widget) {
      widget.addEventListener('contextmenu', function(e) {
        e.preventDefault();
        return false;
      });

      // Add watermarks
      addWatermark();
    }

    // DevTools detection warning
    let devtoolsOpen = false;
    const detectDevTools = () => {
      const threshold = 160;
      if (window.outerWidth - window.innerWidth > threshold ||
          window.outerHeight - window.innerHeight > threshold) {
        if (!devtoolsOpen) {
          devtoolsOpen = true;
          console.clear();
          console.log('%c⚠️ Warning', 'color: red; font-size: 20px; font-weight: bold;');
          console.log('%cThis site\'s assets are protected by copyright.', 'font-size: 14px;');
          console.log('%cUnauthorized downloading or use is prohibited.', 'font-size: 14px;');
        }
      } else {
        devtoolsOpen = false;
      }
    };
    setInterval(detectDevTools, 1000);
  });

  let app = null;
  let currentModel = null;
  let currentModelKey = null;
  let isLoading = false;

  // Wait for all libraries to load
  function waitForLibraries() {
    return new Promise((resolve) => {
      let attempts = 0;
      const maxAttempts = 50;

      const checkLibraries = setInterval(() => {
        attempts++;

        if (window.PIXI && window.PIXI.live2d && window.Live2DCubismCore) {
          clearInterval(checkLibraries);
          resolve();
        } else if (attempts >= maxAttempts) {
          clearInterval(checkLibraries);
          resolve();
        }
      }, 100);
    });
  }

  // Initialize main PIXI Application
  function initApp() {
    const canvas = document.getElementById('live2d-canvas');
    if (!canvas) {
      return null;
    }

    try {
      const app = new PIXI.Application({
        view: canvas,
        width: 800,
        height: 1200,
        backgroundColor: 0x000000,
        backgroundAlpha: 0,
        antialias: true,
        resolution: window.devicePixelRatio || 1,
        autoDensity: true,
        preserveDrawingBuffer: false,
        clearBeforeRender: true,
        powerPreference: 'high-performance'
      });

      return app;
    } catch (error) {
      return null;
    }
  }


  // Setup mouse tracking for main app - only when mouse is over the widget area
  function setupMouseTracking() {
    if (!app) return;

    const mainContainer = document.getElementById('live2d-widget');
    if (!mainContainer) return;

    let lastX = 0;
    let lastY = 0;
    let targetX = 0;
    let targetY = 0;
    let mouseInside = false;
    let resetAnimationId = null;

    // Smooth animation loop for returning to default
    function animateReset() {
      if (!mouseInside && (Math.abs(lastX) > 0.01 || Math.abs(lastY) > 0.01)) {
        // Gradually move towards 0
        lastX *= 0.9;
        lastY *= 0.9;

        if (currentModel && currentModel.internalModel && currentModel.internalModel.coreModel) {
          try {
            currentModel.internalModel.coreModel.setParameterValueById('ParamAngleX', lastX * 30);
            currentModel.internalModel.coreModel.setParameterValueById('ParamAngleY', -lastY * 30);
            currentModel.internalModel.coreModel.setParameterValueById('ParamAngleZ', lastX * 15);
            currentModel.internalModel.coreModel.setParameterValueById('ParamBodyAngleX', lastX * 10);
            currentModel.internalModel.coreModel.setParameterValueById('ParamBodyAngleY', -lastY * 10);
            currentModel.internalModel.coreModel.setParameterValueById('ParamBodyAngleZ', lastX * 8);
            currentModel.internalModel.coreModel.setParameterValueById('ParamEyeBallX', lastX);
            currentModel.internalModel.coreModel.setParameterValueById('ParamEyeBallY', -lastY);
          } catch (e) {
            // Ignore
          }
        }

        resetAnimationId = requestAnimationFrame(animateReset);
      } else {
        // Final reset to exactly 0
        lastX = 0;
        lastY = 0;
        if (currentModel && currentModel.internalModel && currentModel.internalModel.coreModel) {
          try {
            currentModel.internalModel.coreModel.setParameterValueById('ParamAngleX', 0);
            currentModel.internalModel.coreModel.setParameterValueById('ParamAngleY', 0);
            currentModel.internalModel.coreModel.setParameterValueById('ParamAngleZ', 0);
            currentModel.internalModel.coreModel.setParameterValueById('ParamBodyAngleX', 0);
            currentModel.internalModel.coreModel.setParameterValueById('ParamBodyAngleY', 0);
            currentModel.internalModel.coreModel.setParameterValueById('ParamBodyAngleZ', 0);
            currentModel.internalModel.coreModel.setParameterValueById('ParamEyeBallX', 0);
            currentModel.internalModel.coreModel.setParameterValueById('ParamEyeBallY', 0);
          } catch (e) {
            // Ignore
          }
        }
      }
    }

    // Handle mouse/touch movement
    function handleMove(x, y) {
      targetX = x;
      targetY = y;

      // Smooth tracking
      lastX = lastX * 0.7 + targetX * 0.3;
      lastY = lastY * 0.7 + targetY * 0.3;

      if (currentModel && currentModel.internalModel && currentModel.internalModel.coreModel) {
        try {
          currentModel.internalModel.coreModel.setParameterValueById('ParamAngleX', lastX * 30);
          currentModel.internalModel.coreModel.setParameterValueById('ParamAngleY', -lastY * 30);
          currentModel.internalModel.coreModel.setParameterValueById('ParamAngleZ', lastX * 15);
          currentModel.internalModel.coreModel.setParameterValueById('ParamBodyAngleX', lastX * 10);
          currentModel.internalModel.coreModel.setParameterValueById('ParamBodyAngleY', -lastY * 10);
          currentModel.internalModel.coreModel.setParameterValueById('ParamBodyAngleZ', lastX * 8);
          currentModel.internalModel.coreModel.setParameterValueById('ParamEyeBallX', lastX);
          currentModel.internalModel.coreModel.setParameterValueById('ParamEyeBallY', -lastY);
        } catch (e) {
          // Silently ignore parameter errors
        }
      }
    }

    // Mouse events
    mainContainer.addEventListener('mouseenter', () => {
      mouseInside = true;
      if (resetAnimationId) {
        cancelAnimationFrame(resetAnimationId);
        resetAnimationId = null;
      }
    });

    mainContainer.addEventListener('mouseleave', () => {
      mouseInside = false;
      targetX = 0;
      targetY = 0;
      // Start smooth reset animation
      if (!resetAnimationId) {
        resetAnimationId = requestAnimationFrame(animateReset);
      }
    });

    mainContainer.addEventListener('mousemove', (event) => {
      if (!currentModel || !mouseInside) return;

      const rect = mainContainer.getBoundingClientRect();
      const x = ((event.clientX - rect.left) / rect.width - 0.5) * 2;
      const y = ((event.clientY - rect.top) / rect.height - 0.5) * 2;

      handleMove(x, y);
    });

    // Touch events for mobile
    mainContainer.addEventListener('touchstart', (event) => {
      mouseInside = true;
      if (resetAnimationId) {
        cancelAnimationFrame(resetAnimationId);
        resetAnimationId = null;
      }
    });

    mainContainer.addEventListener('touchend', () => {
      mouseInside = false;
      targetX = 0;
      targetY = 0;
      // Start smooth reset animation
      if (!resetAnimationId) {
        resetAnimationId = requestAnimationFrame(animateReset);
      }
    });

    mainContainer.addEventListener('touchmove', (event) => {
      if (!currentModel) return;

      event.preventDefault(); // Prevent scrolling while touching the model

      const touch = event.touches[0];
      const rect = mainContainer.getBoundingClientRect();
      const x = ((touch.clientX - rect.left) / rect.width - 0.5) * 2;
      const y = ((touch.clientY - rect.top) / rect.height - 0.5) * 2;

      handleMove(x, y);
    }, { passive: false });

  }

  // Load and display a Live2D model
  async function loadModel(modelKey) {
    if (isLoading) {
      return;
    }

    if (currentModelKey === modelKey && currentModel) {
      return;
    }

    try {
      isLoading = true;
      const modelData = models[modelKey];

      const container = document.getElementById('live2d-widget');
      if (!container) {
        return;
      }

      // Update background
      container.style.background = modelData.background;

      // Remove previous model from stage if exists
      if (currentModel) {
        if (app && app.stage) {
          app.stage.removeChild(currentModel);
        }
        if (currentModel.destroy) {
          currentModel.destroy({ children: true, texture: true, baseTexture: true });
        }
        currentModel = null;
      }

      // Wait a bit for cleanup
      await new Promise(resolve => setTimeout(resolve, 200));

      // Override fetch to add security headers for Live2D resource requests only
      const originalFetch = window.fetch;
      window.fetch = function(url, options = {}) {
        // Only modify Live2D related requests
        if (url.includes('/static/live2d/') || url.includes('live2d')) {
          // Add X-Requested-With header for Live2D requests
          const modifiedOptions = {
            ...options,
            headers: {
              ...(options.headers || {}),
              'X-Requested-With': 'XMLHttpRequest'
            }
          };
          return originalFetch(url, modifiedOptions);
        }
        // For non-Live2D requests, use original fetch
        return originalFetch(url, options);
      };

      // Load new model
      currentModel = await PIXI.live2d.Live2DModel.from(modelData.path, {
        autoInteract: false,
        autoUpdate: true
      });

      // Restore original fetch after model loads
      window.fetch = originalFetch;

      // Calculate scale - smaller for mobile, full for PC
      const isMobile = window.innerWidth <= 768;
      const scaleX = app.screen.width / currentModel.width;
      const scaleY = app.screen.height / currentModel.height;
      const baseScale = Math.min(scaleX, scaleY);
      const scale = isMobile ? baseScale * 0.6 : baseScale;

      // Set model position and scale - center and fit to screen
      currentModel.scale.set(scale);
      currentModel.x = app.screen.width / 2;
      currentModel.y = app.screen.height / 2;
      currentModel.anchor.set(0.5, 0.5);

      // Enable interactivity
      currentModel.interactive = true;
      currentModel.buttonMode = true;

      // Add model to stage first
      app.stage.addChild(currentModel);

      // Wait a frame for model to be fully initialized, then start animation
      await new Promise(resolve => setTimeout(resolve, 100));

      // Start idle animation if available
      if (currentModel.internalModel && currentModel.internalModel.motionManager) {
        const motionGroups = currentModel.internalModel.motionManager.definitions;
        if (motionGroups && motionGroups['Idle'] && motionGroups['Idle'].length > 0) {
          try {
            await currentModel.motion('Idle', 0, PIXI.live2d.MotionPriority.IDLE);
          } catch (error) {
            // Ignore
          }
        }
      }

      // Store current expression parameters and previous expression name
      let currentExpressionParams = null;
      let previousExpression = null;

      // Handle clicks on model - play random expression
      currentModel.on('pointerdown', async () => {
        if (currentModel.internalModel && currentModel.internalModel.coreModel) {
          try {
            // Reset previous expression if exists
            if (currentExpressionParams) {
              currentExpressionParams.forEach(param => {
                try {
                  currentModel.internalModel.coreModel.setParameterValueById(param.Id, 0);
                } catch (e) {
                  // Ignore
                }
              });
            }

            // List of available expressions
            const expressionNames = ['Happy', 'Angry', 'Surprised', 'Cry', 'Sparkle'];

            // Pick a random expression that's different from the previous one
            let randomExpression;
            do {
              randomExpression = expressionNames[Math.floor(Math.random() * expressionNames.length)];
            } while (randomExpression === previousExpression && expressionNames.length > 1);

            // Load and apply expression file manually
            const expressionPath = `/static/live2d/VTuber_Michelle/${randomExpression}.exp3.json`;

            const response = await fetch(expressionPath, {
              headers: {
                'X-Requested-With': 'XMLHttpRequest'
              }
            });
            if (response.ok) {
              const expressionData = await response.json();

              // Apply expression parameters
              if (expressionData.Parameters) {
                currentExpressionParams = expressionData.Parameters;
                previousExpression = randomExpression;
                expressionData.Parameters.forEach(param => {
                  try {
                    currentModel.internalModel.coreModel.setParameterValueById(param.Id, param.Value);
                  } catch (e) {
                    // Ignore
                  }
                });

                // Reset to default expression after 3 seconds
                setTimeout(() => {
                  if (currentExpressionParams === expressionData.Parameters) {
                    expressionData.Parameters.forEach(param => {
                      try {
                        currentModel.internalModel.coreModel.setParameterValueById(param.Id, 0);
                      } catch (e) {
                        // Ignore
                      }
                    });
                    currentExpressionParams = null;
                    previousExpression = null;
                  }
                }, 3000);
              }
            }
          } catch (error) {
            // Ignore
          }
        }
      });

      currentModelKey = modelKey;

    } catch (error) {
      // Silent error handling
    } finally {
      isLoading = false;
    }
  }

  // Initialize Live2D widget
  async function initLive2D() {
    try {
      // Wait for all dependencies
      await waitForLibraries();

      // Initialize main PIXI Application
      app = initApp();
      if (!app) {
        return;
      }

      // Setup mouse tracking for main app
      setupMouseTracking();

      // Setup button click handlers
      const btnMichelle = document.getElementById('btn-michelle');
      const btnAmamizu = document.getElementById('btn-amamizu');

      if (btnMichelle) {
        btnMichelle.addEventListener('click', () => {
          loadModel('michelle');
        });
      }

      if (btnAmamizu) {
        btnAmamizu.addEventListener('click', () => {
          loadModel('amamizu');
        });
      }

      // Load default model (Amamizu Ai - Extra)
      await loadModel('amamizu');

    } catch (error) {
      // Ignore
    }
  }

  // Start when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initLive2D);
  } else {
    initLive2D();
  }
})();
