
import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
import numpy as np
import math
import time
import threading
# Numba importok eltávolítva a Python 3.14 inkompatibilitás miatt
# A kód tisztán NumPy-t fog használni
NUMBA_AVAILABLE = False

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

        # Azonnal töltsük fel az új helyeket aktív részecskékkel
        dead_indices = np.where(self.particles[:self.max_particles, 6] <= 0)[0]
        if len(dead_indices) > 0:
            # Emit particles to fill all dead slots instantly
            self.emit(0.1, len(dead_indices))


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

            # Add more turbulence and vertical speed for fire effect
            self.particles[idx, 3] = np.random.normal(0, 0.02, count)
            self.particles[idx, 4] = np.random.uniform(0.15, 0.35, count)
            self.particles[idx, 5] = np.random.normal(0, 0.02, count)

            self.particles[idx, 6] = 1.0
            self.particles[idx, 7] = 1.0
            # More varied sizes for flicker
            self.particles[idx, 8] = np.random.uniform(0.4, 0.8, count)

    def update_chunk(self, start, end, dt, frame_scale, wind_force, mouse_ray, interaction_active, interaction_mode):
        """Egy részecske-csoport frissítése (külön szálon futtatható)"""
        chunk = self.particles[start:end]
        
        # 1. Élettartam csökkentése
        chunk[:, 6] -= 0.012 * frame_scale
        
        # 2. Fizika: Szél + Turbulencia
        # Random generálás itt kicsit lassú lehet szálanként, de demonstrációnak jó
        count = end - start
        noise = np.random.normal(0, 0.002, count)
        
        chunk[:, 0] += (chunk[:, 3] + wind_force[0] + noise) * frame_scale
        chunk[:, 1] += (chunk[:, 4] + wind_force[1]) * frame_scale
        chunk[:, 2] += (chunk[:, 5] + wind_force[2]) * frame_scale
        
        # 3. INTERAKCIÓ
        if interaction_active and mouse_ray is not None:
            target_x = mouse_ray[0] * 5 
            target_z = mouse_ray[2] * 5
            
            dx = target_x - chunk[:, 0]
            dz = target_z - chunk[:, 2]
            
            if interaction_mode == 'attract':
                chunk[:, 0] += dx * MOUSE_ATTRACTION * frame_scale
                chunk[:, 2] += dz * MOUSE_ATTRACTION * frame_scale
            else:
                chunk[:, 0] -= dx * MOUSE_ATTRACTION * frame_scale
                chunk[:, 2] -= dz * MOUSE_ATTRACTION * frame_scale

    def update(self, dt, mouse_ray=None, interaction_active=False, interaction_mode='attract', emission_rate=EMISSION_RATE):
        frame_scale = dt * 60.0  
        
        # CPU PÁRHUZAMOSÍTÁS: Több szál indítása
        num_threads = 4
        chunk_size = self.max_particles // num_threads
        threads = []
        
        for i in range(num_threads):
            start = i * chunk_size
            end = start + chunk_size if i < num_threads - 1 else self.max_particles
            if start >= end: continue
            
            t = threading.Thread(target=self.update_chunk, args=(
                start, end, dt, frame_scale, WIND_FORCE, mouse_ray, interaction_active, interaction_mode
            ))
            threads.append(t)
            t.start()
            
        # Megvárjuk, amíg minden szál végez
        for t in threads:
            t.join()

        self.emit(dt, emission_rate)

    def draw(self):
        # GPU PÁRHUZAMOSÍTÁS (Batch Rendering):
        # Ahelyett, hogy egyesével küldenénk a pontokat (lassú),
        # tömbökbe rendezzük őket és egyszerre küldjük át (gyors).
        
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, self.texture_id)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE)
        glDepthMask(GL_FALSE)

        # Csak az élő részecskékkel foglalkozunk
        active_mask = self.particles[:self.max_particles, 6] > 0
        count = np.count_nonzero(active_mask)
        
        if count == 0:
            glDepthMask(GL_TRUE)
            glDisable(GL_TEXTURE_2D)
            return

        # Szűrés
        p_alive = self.particles[:self.max_particles][active_mask]
        
        # Adatok kinyerése
        pos = p_alive[:, 0:3]
        life = p_alive[:, 6]
        size = p_alive[:, 8] * (life ** 0.7)
        
        # Billboard vektorok lekérése
        modelview = glGetDoublev(GL_MODELVIEW_MATRIX)
        right = np.array([modelview[0][0], modelview[1][0], modelview[2][0]])
        up =    np.array([modelview[0][1], modelview[1][1], modelview[2][1]])
        
        # Vektorizált csúcsszámítás (Minden részecskéhez 4 sarokpont)
        right_vec = np.outer(size, right) # (N, 3)
        up_vec = np.outer(size, up)       # (N, 3)
        
        # v1 = pos - right - up
        # v2 = pos + right - up
        # v3 = pos + right + up
        # v4 = pos - right + up
        v1 = pos - right_vec - up_vec
        v2 = pos + right_vec - up_vec
        v3 = pos + right_vec + up_vec
        v4 = pos - right_vec + up_vec
        
        # Összefűzés egyetlen tömbbe a kirajzoláshoz
        vertices = np.empty((count, 4, 3), dtype=np.float32)
        vertices[:, 0] = v1
        vertices[:, 1] = v2
        vertices[:, 2] = v3
        vertices[:, 3] = v4
        vertices = vertices.reshape(-1, 3) # (N*4, 3)
        
        # Textúra koordináták (N*4, 2)
        tex_coords = np.tile(np.array([
            [0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]
        ], dtype=np.float32), (count, 1))
        
        # Színek számítása (vektorizálva)
        colors = np.zeros((count, 4), dtype=np.float32)
        
        # Sárga
        mask1 = life > 0.7
        if np.any(mask1):
            l = life[mask1]
            colors[mask1] = np.column_stack((
                np.ones_like(l), 
                np.full_like(l, 0.95), 
                np.full_like(l, 0.4), 
                np.minimum(1.0, l ** 1.5)
            ))
            
        # Narancs
        mask2 = (life > 0.4) & (life <= 0.7)
        if np.any(mask2):
            l = life[mask2]
            colors[mask2] = np.column_stack((
                np.ones_like(l), 
                0.5 + 0.4 * l, 
                np.full_like(l, 0.1), 
                np.minimum(1.0, l ** 1.2)
            ))
            
        # Piros
        mask3 = life <= 0.4
        if np.any(mask3):
            l = life[mask3]
            colors[mask3] = np.column_stack((
                0.8 * l, 
                np.full_like(l, 0.1), 
                np.zeros_like(l), 
                (l ** 1.1) * 0.7
            ))
            
        # Színek ismétlése 4x minden csúcshoz
        colors_expanded = np.repeat(colors, 4, axis=0)
        
        # Kirajzolás Vertex Array-el (Párhuzamos adatátvitel)
        glEnableClientState(GL_VERTEX_ARRAY)
        glEnableClientState(GL_TEXTURE_COORD_ARRAY)
        glEnableClientState(GL_COLOR_ARRAY)
        
        glVertexPointer(3, GL_FLOAT, 0, vertices)
        glTexCoordPointer(2, GL_FLOAT, 0, tex_coords)
        glColorPointer(4, GL_FLOAT, 0, colors_expanded)
        
        glDrawArrays(GL_QUADS, 0, count * 4)
        
        glDisableClientState(GL_VERTEX_ARRAY)
        glDisableClientState(GL_TEXTURE_COORD_ARRAY)
        glDisableClientState(GL_COLOR_ARRAY)
        
        glDepthMask(GL_TRUE)
        glDisable(GL_TEXTURE_2D)


def main():
    global MAX_PARTICLES, WIND_FORCE, EMISSION_RATE
    pygame.init()
    display = (800, 600)
    pygame.display.set_mode(display, DOUBLEBUF | OPENGL)

    gluPerspective(45, (display[0] / display[1]), 0.1, 50.0)
    glTranslatef(0.0, 0.0, -8)

    system = ParticleSystem(INITIAL_PARTICLES)
    
    x_rot = 20
    y_rot = 0
    mouse_down = False
    interaction_active = False 
    interaction_mode = 'attract'
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
