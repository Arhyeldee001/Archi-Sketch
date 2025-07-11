class FlashlightController {
  constructor() {
    this.flashlightOn = false;
    this.track = null;
    this.isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) || 
                 (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  }

  async init() {
    if (this.isIOS) return false;
    
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: { exact: 'environment' },
          width: { ideal: 1280 },
          height: { ideal: 720 }
        }
      });
      
      this.track = stream.getVideoTracks()[0];
      
      // Wait for video to be ready (important for some Android devices)
      await new Promise(resolve => {
        if (video.readyState >= 2) resolve();
        else video.onloadeddata = resolve;
      });
      
      return true;
    } catch (err) {
      console.error("Camera initialization failed:", err);
      return false;
    }
  }

  async toggle() {
    try {
      if (!this.track) {
        const initialized = await this.init();
        if (!initialized) return false;
      }

      if (this.flashlightOn) {
        await this.turnOff();
      } else {
        await this.turnOn();
      }
      return true;
    } catch (error) {
      console.error("Flashlight toggle error:", error);
      return false;
    }
  }

  async turnOn() {
    if (!this.track) throw new Error('Camera not initialized');
    
    if (this.track.getCapabilities().torch) {
      await this.track.applyConstraints({
        advanced: [{torch: true}]
      });
      this.flashlightOn = true;
      return true;
    }
    throw new Error('Flashlight not supported');
  }

  async turnOff() {
    if (!this.track) return;
    
    await this.track.applyConstraints({
      advanced: [{torch: false}]
    });
    this.flashlightOn = false;
  }

  isSupported() {
    if (this.isIOS) return false;
    return 'mediaDevices' in navigator && 
           'getUserMedia' in navigator.mediaDevices;
  }
}

// Camera and overlay elements
const video = document.getElementById('camera');
const overlay = document.getElementById('overlay');
const upload = document.getElementById('upload');
const opacitySlider = document.getElementById('opacity');
const zoomSlider = document.getElementById('zoom');
const navToggle = document.getElementById('nav-toggle');
const navMenu = document.getElementById('nav-menu');
const resetBtn = document.getElementById('reset-btn');
const flashlight = new FlashlightController();
// API Configuration
const API_BASE_URL = "https://archisketch.onrender.com";
let currentProjectId = null; // To track active project
// State variables
let isDragging = false;
let offsetX = 0;
let offsetY = 0;
let currentScale = 1;
let initialDistance = null;
let initialScale = 1;

// Initialize camera
navigator.mediaDevices.getUserMedia({
  video: { facingMode: { ideal: "environment" } }
})
.then(stream => {
  video.srcObject = stream;
})
.catch(err => {
  alert("Camera error: " + err.message);
});

// Navigation toggle
navToggle.addEventListener('click', () => {
  navMenu.classList.toggle('open');
  navToggle.classList.toggle('open');
});

// Reset button functionality
resetBtn.addEventListener('click', () => {
  overlay.style.display = 'none';
  upload.value = '';
});

// Image upload handler
upload.addEventListener('change', e => {
  const file = e.target.files[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = () => {
    overlay.src = reader.result;
    overlay.style.display = 'block';
    overlay.style.transform = 'translate(-50%, -50%) scale(1)';
    currentScale = 1;
    zoomSlider.value = 1;
  };
  reader.readAsDataURL(file);
});

// Opacity control
opacitySlider.addEventListener('input', () => {
  overlay.style.opacity = opacitySlider.value;
});

// Zoom control
zoomSlider.addEventListener('input', () => {
  currentScale = zoomSlider.value;
  updateTransform();
});

function updateTransform() {
  overlay.style.transform = `translate(-50%, -50%) scale(${currentScale})`;
}

// Touch interaction handlers
overlay.addEventListener('touchstart', e => {
  if (e.touches.length === 1) {
    isDragging = true;
    const touch = e.touches[0];
    offsetX = touch.clientX - overlay.offsetLeft;
    offsetY = touch.clientY - overlay.offsetTop;
  } else if (e.touches.length === 2) {
    isDragging = false;
    initialDistance = getDistance(e.touches[0], e.touches[1]);
    initialScale = currentScale;
  }
});

overlay.addEventListener('touchmove', e => {
  if (e.touches.length === 1 && isDragging) {
    const touch = e.touches[0];
    const left = touch.clientX - offsetX;
    const top = touch.clientY - offsetY;
    overlay.style.left = left + 'px';
    overlay.style.top = top + 'px';
  } else if (e.touches.length === 2) {
    const newDistance = getDistance(e.touches[0], e.touches[1]);
    if (initialDistance) {
      const scaleChange = newDistance / initialDistance;
      currentScale = Math.min(Math.max(initialScale * scaleChange, 0.2), 3);
      zoomSlider.value = currentScale;
      updateTransform();
    }
  }
});

overlay.addEventListener('touchend', e => {
  if (e.touches.length < 2) {
    initialDistance = null;
  }
  if (e.touches.length === 0) {
    isDragging = false;
  }
});

// Helper function for touch distance
function getDistance(touch1, touch2) {
  const dx = touch1.clientX - touch2.clientX;
  const dy = touch1.clientY - touch2.clientY;
  return Math.hypot(dx, dy);
}

// API Functions
async function saveProject(imageData) {
  try {
    const response = await fetch(`${API_BASE_URL}/projects`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image: imageData })
    });
    const data = await response.json();
    currentProjectId = data.id;
    return data;
  } catch (error) {
    console.error("Save error:", error);
    return null;
  }
}

async function loadProjects() {
  try {
    const response = await fetch(`${API_BASE_URL}/projects`);
    return await response.json();
  } catch (error) {
    console.error("Load error:", error);
    return [];
  }
}

// New variables
const imageThumbnails = document.getElementById('image-thumbnails');
const addImageBtn = document.getElementById('add-image-btn');
let currentActiveImage = null;

// Modified upload handler
function handleImageUpload(file) {
  const reader = new FileReader();
  reader.onload = () => {
    // Create thumbnail
    const thumbnail = document.createElement('img');
    thumbnail.className = 'thumbnail';
    thumbnail.src = reader.result;
    
    // Add click handler for thumbnail
    thumbnail.addEventListener('click', () => {
      overlay.src = reader.result;
      overlay.style.display = 'block';
      
      if (currentActiveImage) {
        currentActiveImage.classList.remove('active');
      }
      thumbnail.classList.add('active');
      currentActiveImage = thumbnail;
    });
    
    imageThumbnails.insertBefore(thumbnail, imageThumbnails.firstChild);
    
    if (!currentActiveImage) {
      thumbnail.click();
    }
  };
  reader.readAsDataURL(file);
}

// New image upload button
addImageBtn.addEventListener('click', () => {
  upload.click();
});

// Modified upload event listener
upload.addEventListener('change', e => {
  const files = e.target.files;
  if (!files || files.length === 0) return;
  
  for (let i = 0; i < files.length; i++) {
    handleImageUpload(files[i]);
  }
  
  upload.value = '';
});

// Modified reset function
resetBtn.addEventListener('click', () => {
  overlay.style.display = 'none';
  if (currentActiveImage) {
    currentActiveImage.classList.remove('active');
    currentActiveImage = null;
  }
});

// Reset All button
const resetAllBtn = document.getElementById('reset-all-btn');
resetAllBtn.addEventListener('click', () => {
  imageThumbnails.innerHTML = '';
  imageThumbnails.appendChild(addImageBtn);
  currentActiveImage = null;
  overlay.style.display = 'none';
  overlay.src = '';
  upload.value = '';
});

// Right nav elements
const rightNavToggle = document.getElementById('right-nav-toggle');
const rightNavMenu = document.getElementById('right-nav-menu');
const toggleGridBtn = document.getElementById('toggle-grid-btn');
const toggleFlashlightBtn = document.getElementById('toggle-flashlight-btn');

// Right nav toggle
rightNavToggle.addEventListener('click', () => {
  rightNavMenu.classList.toggle('open');
  rightNavToggle.classList.toggle('open');
});

// Wait for DOM to be fully loaded
document.addEventListener('DOMContentLoaded', async function() {
  // Grid variables
  let gridVisible = false;
  let gridSize = 4; // Default size
  
  // Create grid overlay
  const gridOverlay = document.createElement('div');
  gridOverlay.className = 'grid-overlay';
  document.body.appendChild(gridOverlay);
  
  try {
    const projects = await loadProjects();
    if (projects.length > 0) {
      projects.forEach(project => {
        const thumbnail = document.createElement('img');
        thumbnail.className = 'thumbnail';
        thumbnail.src = project.image;
        thumbnail.addEventListener('click', () => {
          overlay.src = project.image;
          overlay.style.display = 'block';
          currentActiveImage = thumbnail;
        });
        imageThumbnails.insertBefore(thumbnail, imageThumbnails.firstChild);
      });
    }
  } catch (error) {
    console.error("Failed to load projects:", error);
  }

  const toggleGridBtn = document.getElementById('toggle-grid-btn');
  const gridOptions = document.querySelector('.grid-options');
  const gridControls = document.querySelector('.grid-controls');
  
  function updateGrid() {
    if (gridVisible) {
      const cellSize = 100 / gridSize;
      gridOverlay.style.backgroundSize = `${cellSize}% ${cellSize}%`;
      gridOverlay.style.display = 'block';
    } else {
      gridOverlay.style.display = 'none';
    }
  }
  
  toggleGridBtn.addEventListener('click', function(e) {
    e.stopPropagation();
    e.preventDefault();
    console.log('Grid button clicked');
    gridOptions.classList.toggle('show');
  });
  
  document.addEventListener('click', function(e) {
    if (!e.target.closest('.grid-controls')) {
      gridOptions.classList.remove('show');
    }
  });
  
  document.querySelectorAll('.grid-options button').forEach(btn => {
    btn.addEventListener('click', function(e) {
      e.stopPropagation();
      gridSize = parseInt(e.target.dataset.size);
      gridVisible = true;
      updateGrid();
      toggleGridBtn.innerHTML = `<i class="fas fa-th"></i> ${gridSize}×${gridSize}`;
      gridOptions.classList.remove('show');
    });
  });
  
  toggleGridBtn.addEventListener('dblclick', function(e) {
    e.preventDefault();
    gridVisible = !gridVisible;
    updateGrid();
    if (!gridVisible) {
      toggleGridBtn.innerHTML = '<i class="fas fa-th"></i> Grid';
    }
  });
  
  updateGrid();
});

// Improved Flashlight Button Handler
document.getElementById('toggle-flashlight-btn').addEventListener('click', async () => {
  const btn = document.getElementById('toggle-flashlight-btn');
  
  // iOS handling
  if (flashlight.isIOS) {
    btn.innerHTML = '<i class="fas fa-ban"></i> NOT SUPPORTED';
    btn.disabled = true;
    return;
  }

  btn.disabled = true;
  btn.classList.add('loading');
  
  try {
    const success = await flashlight.toggle();
    
    if (success) {
      btn.innerHTML = flashlight.flashlightOn 
        ? '<i class="fas fa-lightbulb"></i> FLASH ON' 
        : '<i class="fas fa-lightbulb"></i> FLASH OFF';
      btn.classList.toggle('active', flashlight.flashlightOn);
    } else {
      btn.innerHTML = '<i class="fas fa-lightbulb"></i> NO FLASH';
    }
  } catch (err) {
    console.error("Flashlight error:", err);
    btn.innerHTML = '<i class="fas fa-ban"></i> NOT SUPPORTED';
  } finally {
    btn.disabled = false;
    btn.classList.remove('loading');
  }
});

// Wait for DOM and all resources to load
window.addEventListener('load', function() {
    const templatePath = localStorage.getItem('selectedTemplatePath');
    
    console.log('AR Page Loaded - Checking for template');
    console.log('Template path from storage:', templatePath);

    if (templatePath) {
        console.log("Loading template:", templatePath);
        
        overlay.onerror = function() {
            console.error("Failed to load template image:", templatePath);
            overlay.alt = "Failed to load template";
            alert("Couldn't load the selected template. Please try again.");
        };

        overlay.onload = function() {
            console.log("Template image loaded successfully");
            overlay.style.display = 'block';
            overlay.style.opacity = 0.7;
            overlay.style.position = 'absolute';
            overlay.style.top = '50%';
            overlay.style.left = '50%';
            overlay.style.transform = 'translate(-50%, -50%)';
            overlay.style.maxWidth = '80%';
            overlay.style.maxHeight = '80%';
            overlay.style.zIndex = '2'; // Changed from 10 to 2 to match uploaded images
        };

        overlay.src = templatePath;
        localStorage.removeItem('selectedTemplatePath');
    }
});
});
