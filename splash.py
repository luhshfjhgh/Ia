import pygame
import sys
import math
import time

def run_splash():
    pygame.init()
    
    # Configurações da tela
    WIDTH, HEIGHT = 800, 600
    screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.NOFRAME)
    pygame.display.set_caption("NOX AI Initialization")
    
    # Cores
    BLACK = (0, 0, 0)
    CYAN = (0, 255, 255)
    BLUE = (0, 100, 255)
    DARK_BLUE = (0, 20, 50)
    WHITE = (255, 255, 255)
    
    clock = pygame.time.Clock()
    font_small = pygame.font.SysFont("Consolas", 14)
    font_large = pygame.font.SysFont("Consolas", 28, bold=True)
    
    start_time = time.time()
    duration = 5  # Duração da splash screen em segundos
    
    # Elementos de texto simulados
    boot_logs = [
        "INITIALIZING NEURAL NETWORK...",
        "LOADING MEMORY CORE...",
        "CALIBRATING SENSORS...",
        "ESTABLISHING CONNECTION...",
        "SYNCING DATABASE...",
        "ACTIVATING COGNITIVE ENGINE...",
        "SECURITY CHECK: PASSED",
        "NOX AI V4.0 READY."
    ]
    
    running = True
    while running:
        elapsed = time.time() - start_time
        progress = min(elapsed / duration, 1.0)
        
        if elapsed >= duration:
            running = False
            
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

        screen.fill(BLACK)
        
        # Desenhar círculos de fundo (HUD)
        center = (WIDTH // 2, HEIGHT // 2)
        radius_base = 150
        
        # Círculo pulsante
        pulse = (math.sin(time.time() * 5) + 1) / 2
        pygame.draw.circle(screen, DARK_BLUE, center, int(radius_base + 10 * pulse), 2)
        pygame.draw.circle(screen, BLUE, center, radius_base, 1)
        
        # Arcos rotativos
        angle = time.time() * 2
        for i in range(4):
            start_angle = angle + (i * math.pi / 2)
            end_angle = start_angle + (math.pi / 4)
            pygame.draw.arc(screen, CYAN, (center[0]-radius_base-20, center[1]-radius_base-20, (radius_base+20)*2, (radius_base+20)*2), start_angle, end_angle, 3)

        # Texto Central
        title_text = font_large.render("NOX AI SYSTEM", True, CYAN)
        screen.blit(title_text, (center[0] - title_text.get_width() // 2, center[1] - title_text.get_height() // 2))
        
        version_text = font_small.render("V4.0 INITIALIZATION", True, BLUE)
        screen.blit(version_text, (center[0] - version_text.get_width() // 2, center[1] + 30))

        # Barra de Progresso
        bar_width = 400
        bar_height = 10
        bar_x = (WIDTH - bar_width) // 2
        bar_y = HEIGHT - 100
        
        pygame.draw.rect(screen, DARK_BLUE, (bar_x, bar_y, bar_width, bar_height))
        pygame.draw.rect(screen, CYAN, (bar_x, bar_y, int(bar_width * progress), bar_height))
        
        # Logs de Boot
        log_index = int(progress * (len(boot_logs) - 1))
        for i in range(max(0, log_index - 5), log_index + 1):
            alpha = 255 - (log_index - i) * 40
            if alpha < 0: alpha = 0
            log_text = font_small.render(boot_logs[i], True, CYAN)
            # Simular transparência desenhando em uma superfície se necessário, 
            # mas para simplicidade aqui usaremos apenas cor fixa ou fade simples
            screen.blit(log_text, (50, 100 + (i - max(0, log_index - 5)) * 20))

        # Efeito de Scanline
        scanline_y = int((time.time() * 200) % HEIGHT)
        pygame.draw.line(screen, (0, 50, 50), (0, scanline_y), (WIDTH, scanline_y), 1)

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()

if __name__ == "__main__":
    run_splash()
