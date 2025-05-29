import pygame
import pygame.camera

# Initialize pygame and camera module
pygame.init()
pygame.camera.init()

# List available cameras
cameras = pygame.camera.list_cameras()
if not cameras:
    print("No camera found!")
    exit()

# Select the first available camera
cam = pygame.camera.Camera(cameras[0], (720, 480))
cam.start()

# Create a display window
screen = pygame.display.set_mode((720, 480))
pygame.display.set_caption("Pygame Camera Preview")

running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    # Capture frame
    frame = cam.get_image()

    # Display frame
    screen.blit(frame, (0, 0))
    pygame.display.update()

# Release resources
cam.stop()
pygame.quit()