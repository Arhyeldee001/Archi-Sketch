// 1. FIRST - Define the FlashlightController class
class FlashlightController {
  constructor() {
    this.flashlightOn = false;
  }

  async toggle() {
    try {
      if (this.flashlightOn) {
        await this.turnOff();
      } else {
        await this.turnOn();
      }
      return true;
    } catch (error) {
      console.error("Flashlight error:", error);
      return false;
    }
  }

  async turnOn() {
    if (!video.srcObject) throw new Error('Camera not initialized');
    
    const videoTrack = video.srcObject.getVideoTracks()[0];
    if (videoTrack.getCapabilities().torch) {
      await videoTrack.applyConstraints({
        advanced: [{torch: true}]
      });
      this.flashlightOn = true;
      return true;
    }
    throw new Error('Flashlight not supported');
  }

  async turnOff() {
    if (!video.srcObject) return;
    
    const videoTrack = video.srcObject.getVideoTracks()[0];
    await videoTrack.applyConstraints({
      advanced: [{torch: false}]
    });
    this.flashlightOn = false;
  }

  isSupported() {
    if (!video.srcObject) return false;
    const track = video.srcObject.getVideoTracks()[0];
    return track.getCapabilities().torch;
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
// Update your existing navigation toggle code to:
navToggle.addEventListener('click', () => {
  navMenu.classList.toggle('open');
  navToggle.classList.toggle('open');
  // No need to manually change icons - CSS handles it
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

// ... (keep all existing variable declarations)

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
      // Set this image as active in AR view
      overlay.src = reader.result;
      overlay.style.display = 'block';
      
      // Update active state
      if (currentActiveImage) {
        currentActiveImage.classList.remove('active');
      }
      thumbnail.classList.add('active');
      currentActiveImage = thumbnail;
    });
    
    // Add to thumbnails container (at the top)
    imageThumbnails.insertBefore(thumbnail, imageThumbnails.firstChild);
    
    // If first image, activate it automatically
    if (!currentActiveImage) {
      thumbnail.click();
    }
  };
  reader.readAsDataURL(file);
}

// New image upload button
addImageBtn.addEventListener('click', () => {
  upload.click(); // Trigger hidden file input
});

// Modified upload event listener
upload.addEventListener('change', e => {
  const files = e.target.files;
  if (!files || files.length === 0) return;
  
  for (let i = 0; i < files.length; i++) {
    handleImageUpload(files[i]);
  }
  
  // Reset input to allow same file to be uploaded again
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

// Get the Reset All button (add this with your other element declarations at the top)
const resetAllBtn = document.getElementById('reset-all-btn');

// Reset All button functionality (add this near your other event listeners)
resetAllBtn.addEventListener('click', () => {
  // Clear all thumbnails
  imageThumbnails.innerHTML = '';
  
  // Re-add the add-image button (since we cleared everything)
  imageThumbnails.appendChild(addImageBtn);
  
  // Clear the current active image reference
  currentActiveImage = null;
  
  // Optional: Also reset the AR view if you want
  overlay.style.display = 'none';
  overlay.src = '';
  
  // Optional: Reset file input
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
document.addEventListener('DOMContentLoaded', function() {
  // Grid variables
  let gridVisible = false;
  let gridSize = 4; // Default size
  
  // Create grid overlay
  const gridOverlay = document.createElement('div');
  gridOverlay.className = 'grid-overlay';
  document.body.appendChild(gridOverlay); // Changed from #app to body
  
  // Get elements
  const toggleGridBtn = document.getElementById('toggle-grid-btn');
  const gridOptions = document.querySelector('.grid-options');
  const gridControls = document.querySelector('.grid-controls');
  
  // Function to update grid display
  function updateGrid() {
    if (gridVisible) {
      const cellSize = 100 / gridSize;
      gridOverlay.style.backgroundSize = `${cellSize}% ${cellSize}%`;
      gridOverlay.style.display = 'block';
    } else {
      gridOverlay.style.display = 'none';
    }
  }
  
  // Toggle grid options visibility
  toggleGridBtn.addEventListener('click', function(e) {
    e.stopPropagation();
    e.preventDefault(); // Add this to prevent any default behavior
    console.log('Grid button clicked');
    gridOptions.classList.toggle('show');
  });
  
  // Close grid options when clicking elsewhere
  document.addEventListener('click', function(e) {
    if (!e.target.closest('.grid-controls')) {
      gridOptions.classList.remove('show');
    }
  });
  
  // Grid size selection
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
  
  // Toggle grid visibility on double click
  toggleGridBtn.addEventListener('dblclick', function(e) {
    e.preventDefault();
    gridVisible = !gridVisible;
    updateGrid();
    if (!gridVisible) {
      toggleGridBtn.innerHTML = '<i class="fas fa-th"></i> Grid';
    }
  });
  
  // Initialize grid
  updateGrid();
});

// Flashlight toggle
toggleFlashlightBtn.addEventListener('click', async () => {
  // Check support first
  if (!flashlight.isSupported()) {
    toggleFlashlightBtn.innerHTML = '<i class="fas fa-ban"></i> Not Supported';
    toggleFlashlightBtn.disabled = true;
    return;
  }

  const success = await flashlight.toggle();
  if (success) {
    toggleFlashlightBtn.classList.toggle('active', flashlight.flashlightOn);
    toggleFlashlightBtn.innerHTML = flashlight.flashlightOn 
      ? '<i class="fas fa-lightbulb"></i> FLASH ON'
      : '<i class="fas fa-lightbulb"></i> FLASH OFF';
  } else {
    toggleFlashlightBtn.innerHTML = '<i class="fas fa-ban"></i> Error';
  }
});

// Wait for DOM and all resources to load
window.addEventListener('load', function() {
    const templatePath = localStorage.getItem('selectedTemplatePath');
    
    // Debugging logs
    console.log('AR Page Loaded - Checking for template');
    console.log('Template path from storage:', templatePath);

    if (templatePath) {
        console.log("Loading template:", templatePath);
        
        // Error handling
        overlay.onerror = function() {
            console.error("Failed to load template image:", templatePath);
            overlay.alt = "Failed to load template";
            alert("Couldn't load the selected template. Please try again.");
        };

        // When image loads successfully
        overlay.onload = function() {
            console.log("Template image loaded successfully");
            overlay.style.display = 'block';
            overlay.style.opacity = 0.7;
            
            // Center the image (if not already handled by your CSS)
            overlay.style.position = 'absolute';
            overlay.style.top = '50%';
            overlay.style.left = '50%';
            overlay.style.transform = 'translate(-50%, -50%)';
            overlay.style.maxWidth = '80%';
            overlay.style.maxHeight = '80%';
            overlay.style.zIndex = '10';
        };

        // Set the image source (this triggers loading)
        overlay.src = templatePath;
        
        // Clear storage after loading
        localStorage.removeItem('selectedTemplatePath');
    }
});