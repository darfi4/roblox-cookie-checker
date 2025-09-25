class ParticleSystem {
    constructor() {
        this.particles = [];
        this.mouseX = 0;
        this.mouseY = 0;
        this.container = document.getElementById('particles-js');
        if (this.container) {
            this.init();
        }
    }

    init() {
        this.createParticles();
        this.setupEventListeners();
        this.animate();
    }

    createParticles() {
        const particleCount = window.innerWidth < 768 ? 30 : 80;
        
        for (let i = 0; i < particleCount; i++) {
            this.particles.push(this.createParticle());
        }
    }

    createParticle() {
        const particle = document.createElement('div');
        particle.className = 'particle';
        
        const size = Math.random() * 4 + 2;
        const posX = Math.random() * 100;
        const posY = Math.random() * 100;
        const duration = Math.random() * 20 + 20;
        const delay = Math.random() * 5;
        const color = this.getRandomColor();
        
        particle.style.cssText = `
            position: absolute;
            width: ${size}px;
            height: ${size}px;
            background: ${color};
            border-radius: 50%;
            left: ${posX}vw;
            top: ${posY}vh;
            opacity: ${Math.random() * 0.6 + 0.2};
            pointer-events: none;
            animation: float${Math.floor(Math.random() * 3) + 1} ${duration}s linear infinite ${delay}s;
            filter: blur(${Math.random() * 2}px);
            box-shadow: 0 0 ${size * 2}px ${size}px ${color}20;
            transition: all 0.3s ease;
        `;
        
        this.container.appendChild(particle);
        
        return {
            element: particle,
            x: posX,
            y: posY,
            vx: (Math.random() - 0.5) * 0.2,
            vy: (Math.random() - 0.5) * 0.2,
            size: size,
            originalSize: size,
            color: color
        };
    }

    getRandomColor() {
        const colors = [
            '#6366f1', '#10b981', '#8b5cf6', '#06b6d4', '#f59e0b', '#ef4444'
        ];
        return colors[Math.floor(Math.random() * colors.length)];
    }

    setupEventListeners() {
        document.addEventListener('mousemove', (e) => {
            this.mouseX = e.clientX;
            this.mouseY = e.clientY;
        });

        window.addEventListener('resize', () => {
            this.particles.forEach(particle => {
                if (particle.element.parentNode) {
                    particle.element.remove();
                }
            });
            this.particles = [];
            this.createParticles();
        });
    }

    animate() {
        this.particles.forEach(particle => {
            const dx = this.mouseX - particle.x * window.innerWidth / 100;
            const dy = this.mouseY - particle.y * window.innerHeight / 100;
            const distance = Math.sqrt(dx * dx + dy * dy);
            
            if (distance < 150) {
                const force = (150 - distance) / 150;
                particle.vx -= (dx / distance) * force * 0.1;
                particle.vy -= (dy / distance) * force * 0.1;
                
                particle.size = particle.originalSize * (1 + force * 2);
                particle.element.style.width = `${particle.size}px`;
                particle.element.style.height = `${particle.size}px`;
                particle.element.style.opacity = Math.min(0.8, 0.2 + force * 0.6);
            } else {
                particle.size += (particle.originalSize - particle.size) * 0.1;
                particle.element.style.width = `${particle.size}px`;
                particle.element.style.height = `${particle.size}px`;
                particle.element.style.opacity = 0.2 + (particle.originalSize / 6) * 0.4;
            }
            
            particle.x += particle.vx;
            particle.y += particle.vy;
            
            if (particle.x < 0 || particle.x > 100) particle.vx *= -1;
            if (particle.y < 0 || particle.y > 100) particle.vy *= -1;
            
            particle.x = Math.max(0, Math.min(100, particle.x));
            particle.y = Math.max(0, Math.min(100, particle.y));
            
            particle.vx *= 0.98;
            particle.vy *= 0.98;
            
            particle.element.style.left = `${particle.x}vw`;
            particle.element.style.top = `${particle.y}vh`;
        });
        
        requestAnimationFrame(() => this.animate());
    }
}

// Добавляем CSS анимации для частиц
const addParticleStyles = () => {
    const style = document.createElement('style');
    style.textContent = `
        @keyframes float1 {
            0%, 100% { transform: translate(0, 0) scale(1); }
            25% { transform: translate(10px, -5px) scale(1.1); }
            50% { transform: translate(5px, -10px) scale(0.9); }
            75% { transform: translate(-5px, -5px) scale(1.05); }
        }
        
        @keyframes float2 {
            0%, 100% { transform: translate(0, 0) scale(1); }
            25% { transform: translate(-8px, 8px) scale(1.2); }
            50% { transform: translate(8px, 5px) scale(0.8); }
            75% { transform: translate(-5px, -8px) scale(1.1); }
        }
        
        @keyframes float3 {
            0%, 100% { transform: translate(0, 0) scale(1); }
            25% { transform: translate(12px, 3px) scale(1.15); }
            50% { transform: translate(-6px, 12px) scale(0.85); }
            75% { transform: translate(3px, -6px) scale(1.05); }
        }
    `;
    document.head.appendChild(style);
};

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    addParticleStyles();
    new ParticleSystem();
});