// Улучшенная версия particles.js
class ParticleSystem {
    constructor() {
        this.particles = [];
        this.mouseX = 0;
        this.mouseY = 0;
        this.container = document.getElementById('particles-js');
        this.init();
    }

    init() {
        this.createParticles();
        this.setupEventListeners();
        this.animate();
    }

    createParticles() {
        const particleCount = window.innerWidth < 768 ? 50 : 150;
        
        for (let i = 0; i < particleCount; i++) {
            this.particles.push(this.createParticle());
        }
    }

    createParticle() {
        const particle = document.createElement('div');
        particle.className = 'particle';
        
        const size = Math.random() * 5 + 1;
        const posX = Math.random() * 100;
        const posY = Math.random() * 100;
        const duration = Math.random() * 30 + 20;
        const delay = Math.random() * 10;
        const color = this.getRandomColor();
        
        particle.style.cssText = `
            position: absolute;
            width: ${size}px;
            height: ${size}px;
            background: ${color};
            border-radius: 50%;
            left: ${posX}vw;
            top: ${posY}vh;
            opacity: ${Math.random() * 0.8 + 0.2};
            pointer-events: none;
            animation: float${Math.floor(Math.random() * 4) + 1} ${duration}s ease-in-out infinite ${delay}s;
            filter: blur(${Math.random() * 3}px);
            box-shadow: 0 0 ${size * 3}px ${size}px ${color}40;
            transition: all 0.3s ease;
        `;
        
        this.container.appendChild(particle);
        
        return {
            element: particle,
            x: posX,
            y: posY,
            vx: (Math.random() - 0.5) * 0.5,
            vy: (Math.random() - 0.5) * 0.5,
            size: size,
            originalSize: size,
            color: color,
            inertia: Math.random() * 0.1 + 0.9
        };
    }

    getRandomColor() {
        const colors = [
            '#6366f1', '#10b981', '#8b5cf6', '#06b6d4', '#f59e0b', '#ef4444',
            '#ec4899', '#84cc16', '#f97316', '#6b7280'
        ];
        return colors[Math.floor(Math.random() * colors.length)];
    }

    setupEventListeners() {
        document.addEventListener('mousemove', (e) => {
            this.mouseX = e.clientX;
            this.mouseY = e.clientY;
        });

        window.addEventListener('resize', () => {
            this.container.innerHTML = '';
            this.particles = [];
            this.createParticles();
        });
    }

    animate() {
        const centerX = window.innerWidth / 2;
        const centerY = window.innerHeight / 2;
        
        this.particles.forEach(particle => {
            const rect = particle.element.getBoundingClientRect();
            const particleX = rect.left + rect.width / 2;
            const particleY = rect.top + rect.height / 2;
            
            const dx = this.mouseX - particleX;
            const dy = this.mouseY - particleY;
            const distance = Math.sqrt(dx * dx + dy * dy);
            
            if (distance < 200) {
                const force = (200 - distance) / 200;
                const angle = Math.atan2(dy, dx);
                
                particle.vx += Math.cos(angle) * force * 0.1;
                particle.vy += Math.sin(angle) * force * 0.1;
                
                const newSize = particle.originalSize + force * 5;
                particle.element.style.width = `${newSize}px`;
                particle.element.style.height = `${newSize}px`;
                particle.element.style.opacity = 0.8;
            } else {
                particle.vx *= particle.inertia;
                particle.vy *= particle.inertia;
                
                particle.element.style.width = `${particle.originalSize}px`;
                particle.element.style.height = `${particle.originalSize}px`;
                particle.element.style.opacity = 0.4 + Math.random() * 0.4;
            }
            
            particle.x += particle.vx;
            particle.y += particle.vy;
            
            // Ограничение движения частиц
            if (particle.x < 0 || particle.x > 100) particle.vx *= -1;
            if (particle.y < 0 || particle.y > 100) particle.vy *= -1;
            
            particle.element.style.left = `${Math.max(0, Math.min(100, particle.x))}vw`;
            particle.element.style.top = `${Math.max(0, Math.min(100, particle.y))}vh`;
        });
        
        requestAnimationFrame(() => this.animate());
    }
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    new ParticleSystem();
});

// Добавление CSS анимаций
const style = document.createElement('style');
style.textContent = `
    @keyframes float1 {
        0%, 100% { transform: translate(0, 0) rotate(0deg); }
        25% { transform: translate(10px, -15px) rotate(90deg); }
        50% { transform: translate(-5px, 10px) rotate(180deg); }
        75% { transform: translate(-10px, -5px) rotate(270deg); }
    }
    
    @keyframes float2 {
        0%, 100% { transform: translate(0, 0) scale(1); }
        50% { transform: translate(-15px, 10px) scale(1.1); }
    }
    
    @keyframes float3 {
        0%, 100% { transform: translate(0, 0) skew(0deg); }
        33% { transform: translate(12px, 8px) skew(5deg); }
        66% { transform: translate(-8px, -12px) skew(-5deg); }
    }
    
    @keyframes float4 {
        0% { transform: translate(0, 0) rotate(0deg); }
        100% { transform: translate(20px, -20px) rotate(360deg); }
    }
`;
document.head.appendChild(style);