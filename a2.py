
import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
import numpy as np
import math
import time
try:
    from numba import njit, prange
    NUMBA_AVAILABLE = True
except Exception:
    NUMBA_AVAILABLE = False

# --- Numba gyorsított frissítés (opcionális) ---
try:
    from numba import njit, prange
    @njit(parallel=True)
    def _numba_update(active_slice, n, frame_scale, wind_x, wind_y, wind_z,
                      target_x, target_z, mouse_attr, mode_sign):
        for i in prange(n):
            active_slice[i, 6] -= 0.012 * frame_scale
            noise = ((i * 16807) % 1000) / 1000.0 - 0.5
            nx = noise * 0.004 * frame_scale
            active_slice[i, 0] += (active_slice[i, 3] + wind_x) * frame_scale + nx
            active_slice[i, 1] += (active_slice[i, 4] + wind_y) * frame_scale
            active_slice[i, 2] += (active_slice[i, 5] + wind_z) * frame_scale
            if mouse_attr > 0.0:
                dx = target_x - active_slice[i, 0]
                dz = target_z - active_slice[i, 2]
                active_slice[i, 0] += mode_sign * dx * mouse_attr * frame_scale
                active_slice[i, 2] += mode_sign * dz * mouse_attr * frame_scale
except Exception:
    def _numba_update(active_slice, n, frame_scale, wind_x, wind_y, wind_z,
                      target_x, target_z, mouse_attr, mode_sign):
        # Dummy: nem csinál semmit, NumPy útvonal fut helyette
        pass

# --- KONFIGURÁCIÓ ---
SCREEN_WIDTH = 1000
SCREEN_HEIGHT = 800
# Kezdeti részecskeszám, de futás közben változtatható
INITIAL_PARTICLES = 1000 
PARTICLE_STEP = 500       # Ennyivel növekszik/csökken a szám
EMISSION_RATE = 30 
MOUSE_ATTRACTION = 0.005
MAX_PARTICLES = INITIAL_PARTICLES # Globális terhelésváltozó

# Fizika (globális változó, a billentyűk módosítják)
WIND_FORCE = np.array([0.0, 0.0, 0.0]) 

# --- SEGÉDFÜGGVÉNYEK ---

def create_fire_texture():
    """Generál egy 64x64-es Gaussian-alapú puha textúrát."""
    size = 64
    texture_data = np.zeros((size, size, 4), dtype=np.uint8)
    center = size / 2
    radius = size / 2

    for y in range(size):
        for x in range(size):
            dist = math.sqrt((x - center)**2 + (y - center)**2)
            dist_norm = dist / radius
            if dist_norm < 1.0:
                alpha = int(255 * (math.exp(-3 * dist_norm**2)))
                texture_data[y, x] = [255, 255, 255, alpha]
            else:
                texture_data[y, x] = [0, 0, 0, 0]

    tex_id = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, tex_id)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, size, size, 0, GL_RGBA, GL_UNSIGNED_BYTE, texture_data)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    return tex_id

def draw_grid():
    """Segédrács a térérzet javítására"""
    glDisable(GL_TEXTURE_2D)
    glLineWidth(1)
    glColor4f(0.3, 0.3, 0.3, 1.0)
    
    glBegin(GL_LINES)
    for i in range(-10, 11):
        glVertex3f(i, -2, -10)
        glVertex3f(i, -2, 10)
        glVertex3f(-10, -2, i)
        glVertex3f(10, -2, i)
    glEnd()

def get_mouse_ray(mouse_x, mouse_y, width, height):
    x = (2.0 * mouse_x) / width - 1.0
    y = 1.0 - (2.0 * mouse_y) / height
    return np.array([x, y, 1.0])

# --- RÉSZECSKE RENDSZER (PARTICLE SYSTEM) OSZTÁLY ---

class ParticleSystem:
    def __init__(self, initial_count):
        self.max_particles = initial_count
        self.particles = self._initialize_particles(initial_count)
        self.texture_id = create_fire_texture()
        self._emit_accum = 0.0  # frakcionális emisszió felhalmozó (dt-hez)

    def _initialize_particles(self, count):
        """Inicializálja a részecsketömböt"""
        # [x, y, z, vx, vy, vz, life, max_life, size, r, g, b, a]
        new_particles = np.zeros((count, 13), dtype=np.float32)
        new_particles[:, 6] = -1.0 
        return new_particles

    def resize_particles(self, new_count):
        """
        Terhelés-szabályozó: Átméretezi a részecsketömböt.
        Ez a függvény lehetővé teszi a terhelés változtatását futás közben.
        """
        if new_count == self.max_particles:
            return
        
        old_count = self.max_particles
        old_particles = self.particles
        
        # Új, üres tömb létrehozása
        self.particles = self._initialize_particles(new_count)
        
        # Át másoljuk a régi, élő részecskéket
        copy_count = min(old_count, new_count)
        self.particles[:copy_count] = old_particles[:copy_count]
        
        self.max_particles = new_count
        print(f"Resized particle system to {new_count} particles.")


    def emit(self, dt, emission_rate):
        """Új részecskék kibocsátása dt-hez igazítva."""
        dead_indices = np.where(self.particles[:self.max_particles, 6] <= 0)[0]
        target = emission_rate * dt + self._emit_accum
        count = int(target)
        self._emit_accum = target - count
        count = min(len(dead_indices), count)

        if count > 0:
            idx = dead_indices[:count]

            angle = np.random.uniform(0, 2*math.pi, count)
            radius = np.random.uniform(0, 0.3, count)

            self.particles[idx, 0] = np.cos(angle) * radius
            self.particles[idx, 1] = -1.5
            self.particles[idx, 2] = np.sin(angle) * radius

            self.particles[idx, 3] = np.random.normal(0, 0.01, count)
            self.particles[idx, 4] = np.random.uniform(0.08, 0.2, count)
            self.particles[idx, 5] = np.random.normal(0, 0.01, count)

            self.particles[idx, 6] = 1.0
            self.particles[idx, 7] = 1.0
            self.particles[idx, 8] = np.random.uniform(0.3, 0.6, count)

    def update(self, dt, mouse_ray=None, interaction_active=False, interaction_mode='attract', emission_rate=EMISSION_RATE):
        # 1. Élettartam (csak az aktív részecskéken)
        active_slice = self.particles[:self.max_particles]
        frame_scale = dt * 60.0  # 60 FPS-hez igazított skálázás (megtartja a jelenlegi tempót)
        if NUMBA_AVAILABLE:
            target_x = mouse_ray[0] * 5 if (interaction_active and mouse_ray is not None) else 0.0
            target_z = mouse_ray[2] * 5 if (interaction_active and mouse_ray is not None) else 0.0
            mode_sign = 1.0 if interaction_mode == 'attract' else -1.0
            _numba_update(active_slice, self.max_particles, frame_scale, WIND_FORCE[0], WIND_FORCE[1], WIND_FORCE[2],
                          target_x, target_z, MOUSE_ATTRACTION if interaction_active and mouse_ray is not None else 0.0,
                          mode_sign)
        else:
            active_slice[:, 6] -= 0.012 * frame_scale
            
            # 2. Fizika: Szél + Turbulencia
            active_slice[:, 0] += (active_slice[:, 3] + WIND_FORCE[0] + np.random.normal(0, 0.002, self.max_particles)) * frame_scale
            active_slice[:, 1] += (active_slice[:, 4] + WIND_FORCE[1]) * frame_scale
            active_slice[:, 2] += (active_slice[:, 5] + WIND_FORCE[2]) * frame_scale
            
            # 3. INTERAKCIÓ: Vonzás vagy Taszítás
            if interaction_active and mouse_ray is not None:
                
                target_x = mouse_ray[0] * 5 
                target_z = mouse_ray[2] * 5
                
                dx = target_x - active_slice[:, 0]
                dz = target_z - active_slice[:, 2]
                
                if interaction_mode == 'attract':
                    active_slice[:, 0] += dx * MOUSE_ATTRACTION * frame_scale
                    active_slice[:, 2] += dz * MOUSE_ATTRACTION * frame_scale
                else:
                    active_slice[:, 0] -= dx * MOUSE_ATTRACTION * frame_scale
                    active_slice[:, 2] -= dz * MOUSE_ATTRACTION * frame_scale

        self.emit(dt, emission_rate)

    def draw(self):
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, self.texture_id)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE)
        glDepthMask(GL_FALSE)

        modelview = glGetDoublev(GL_MODELVIEW_MATRIX)
        right = np.array([modelview[0][0], modelview[1][0], modelview[2][0]])
        up =    np.array([modelview[0][1], modelview[1][1], modelview[2][1]])
        
        # Csak a jelenleg aktív részecskéken iterálunk (a MAX_PARTICLES alapján)
        glBegin(GL_QUADS)
        for p in self.particles[:self.max_particles]: 
            life = p[6]
            if life <= 0: continue
            
            pos = p[0:3]
            size = p[8] * life 
            
            # Szín
            if life > 0.5:
                glColor4f(1.0, 0.9, 0.4, life)
            else:
                glColor4f(0.8, 0.2, 0.0, life * 0.8)

            v1 = pos + (right * -size) + (up * -size)
            v2 = pos + (right * size) + (up * -size)
            v3 = pos + (right * size) + (up * size)
            v4 = pos + (right * -size) + (up * size)
            
            glTexCoord2f(0, 0); glVertex3f(v1[0], v1[1], v1[2])
            glTexCoord2f(1, 0); glVertex3f(v2[0], v2[1], v2[2])
            glTexCoord2f(1, 1); glVertex3f(v3[0], v3[1], v3[2])
            glTexCoord2f(0, 1); glVertex3f(v4[0], v4[1], v4[2])

        glEnd()
        
        glDepthMask(GL_TRUE)
        glDisable(GL_TEXTURE_2D)

# --- FŐ PROGRAM ---

def main():
    global MAX_PARTICLES, WIND_FORCE, EMISSION_RATE
    pygame.init()
    display = (SCREEN_WIDTH, SCREEN_HEIGHT)
    pygame.display.set_mode(display, DOUBLEBUF | OPENGL | RESIZABLE)
    pygame.display.set_caption("Advanced Fire Simulation - Terhelés-szabályozás (Z/X)")

    gluPerspective(45, (display[0] / display[1]), 0.1, 50.0)
    glTranslatef(0.0, 0.0, -8)

    # Részecskerendszer létrehozása a kezdeti terheléssel
    system = ParticleSystem(INITIAL_PARTICLES)
    
    x_rot = 20
    y_rot = 0
    mouse_down = False
    interaction_active = False # Jobb egérgomb interakció
    interaction_mode = 'attract' # Kezdeti mód
    paused = False
    show_grid = True
    
    clock = pygame.time.Clock()
    caption_timer = 0.0
    cpu_time_ms = 0.0
    gpu_time_ms = 0.0

    while True:
        dt = clock.tick(60) / 1000.0
        mouse_pos = pygame.mouse.get_pos()
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); return
            elif event.type == VIDEORESIZE:
                display = (event.w, event.h)
                pygame.display.set_mode(display, DOUBLEBUF | OPENGL | RESIZABLE)
                glViewport(0, 0, display[0], display[1])
                glMatrixMode(GL_PROJECTION)
                glLoadIdentity()
                gluPerspective(45, (display[0] / display[1]), 0.1, 50.0)
                glMatrixMode(GL_MODELVIEW)
            
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1: mouse_down = True
                if event.button == 3: interaction_active = True
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1: mouse_down = False
                if event.button == 3: interaction_active = False
            
            elif event.type == pygame.MOUSEMOTION:
                if mouse_down:
                    dx, dy = pygame.mouse.get_rel()
                    y_rot += dx * 0.5
                    x_rot += dy * 0.5
                else:
                    pygame.mouse.get_rel()
            
            elif event.type == pygame.KEYDOWN:
                # SPACE: Váltás vonzás és taszítás között
                if event.key == pygame.K_SPACE:
                    if interaction_mode == 'attract':
                        interaction_mode = 'repel'
                        print("Interaction Mode: REPULSION (Taszítás/Fújás)")
                    else:
                        interaction_mode = 'attract'
                        print("Interaction Mode: ATTRACTION (Vonzás/Követés)")
                
                # Z: Terhelés csökkentése
                elif event.key == pygame.K_z:
                    new_count = max(PARTICLE_STEP, system.max_particles - PARTICLE_STEP)
                    system.resize_particles(new_count)
                
                # X: Terhelés növelése
                elif event.key == pygame.K_x:
                    new_count = system.max_particles + PARTICLE_STEP
                    system.resize_particles(new_count)

                # P: Szünet
                elif event.key == pygame.K_p:
                    paused = not paused
                    print(f"Paused: {paused}")

                # G: Rács ki/be
                elif event.key == pygame.K_g:
                    show_grid = not show_grid
                
                # C/V: Emisszió csökkentése/növelése
                elif event.key == pygame.K_c:
                    EMISSION_RATE = max(1, EMISSION_RATE - 5)
                    print(f"Emission rate: {EMISSION_RATE}/s")
                elif event.key == pygame.K_v:
                    EMISSION_RATE = min(5000, EMISSION_RATE + 5)
                    print(f"Emission rate: {EMISSION_RATE}/s")

                # ESC: Kilépés
                elif event.key == pygame.K_ESCAPE:
                    pygame.quit(); return

        # Szél irányítása (Nyilak)
        keys = pygame.key.get_pressed()
        WIND_FORCE[0] = (keys[pygame.K_RIGHT] - keys[pygame.K_LEFT]) * 0.02
        WIND_FORCE[1] = (keys[pygame.K_UP] - keys[pygame.K_DOWN]) * 0.01

        # Logika frissítése (CPU mérés)
        if not paused:
            ray = get_mouse_ray(mouse_pos[0], mouse_pos[1], display[0], display[1])
            cpu_start = time.perf_counter()
            system.update(dt, mouse_ray=ray, interaction_active=interaction_active, interaction_mode=interaction_mode, emission_rate=EMISSION_RATE)
            cpu_time_ms = (time.perf_counter() - cpu_start) * 1000.0

        # Renderelés (GPU mérés)
        gpu_start = time.perf_counter()
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        gluPerspective(45, (display[0] / display[1]), 0.1, 50.0)
        glTranslatef(0.0, 0.0, -8)

        glRotatef(x_rot, 1, 0, 0)
        glRotatef(y_rot, 0, 1, 0)

        if show_grid:
            draw_grid()
        system.draw()
        gpu_time_ms = (time.perf_counter() - gpu_start) * 1000.0

        pygame.display.flip()

        # Ablakcím frissítése időnként (FPS, részecskék, emisszió, módok, CPU/GPU ms)
        caption_timer += dt
        if caption_timer >= 0.5:
            caption_timer = 0.0
            fps = clock.get_fps()
            pygame.display.set_caption(
                f"Fire Simulation | FPS: {fps:.1f} | Particles: {system.max_particles} | Emit: {EMISSION_RATE}/s | Mode: {interaction_mode.upper()} | Paused: {paused} | CPU: {cpu_time_ms:.2f}ms | GPU: {gpu_time_ms:.2f}ms"
            )

if __name__ == "__main__":
    main()
