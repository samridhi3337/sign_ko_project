import pygame
import time

pygame.mixer.init()
pygame.mixer.music.load("alarm.mp3")

# -1 means repeat forever
pygame.mixer.music.play(-1)

time.sleep(10)