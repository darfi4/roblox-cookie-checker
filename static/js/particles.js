class ParticleSystem {
    constructor(canvas) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        this.particles = [];
        this.mouse = { x: undefined, y: undefined, radius: 150 };
        this.interactionStrength = 8;
        this.connectionDistance = 120;
        
        this.init();
        this.animate();
        this.bindEvents();
    }
    
    init() {
        this.resize();
        this.createParticles(60); // Уменьшил количество для производительности
    }
    
    resize() {
        this.canvas.width = window.innerWidth;
        this.canvas.height = window.innerHeight;
        this.createParticles(0); // Пересоздаем частицы при изменении размера
    }
    
    createParticles(count) {
        const colors = [
            'hsl(265, 100%, 60%)', // Яркий фиолетовый
            'hsl(180, 100%, 50%)', // Циан
            'hsl(300, 100%, 60%)', // Розовый
            'hsl(120, 100%, 50%)'  // Зеленый
        ];
        
        // Сохраняем существующие частицы если пересоздаем
        const existingParticles = this.particles.slice(0, this.particles.length - count);
        this.particles = existingParticles;
        
        for (let i = 0; i < count; i++) {
            this.particles.push({
                x: Math.random() * this.canvas.width,
                y: Math.random() * this.canvas.height,
                size: Math.random() * 3 + 1,
                speedX: (Math.random() - 0.5) * 2,
                speedY: (Math.random() - 0.5) * 2,
                color: colors[Math.floor(Math.random() * colors.length)],
                opacity: Math.random() * 0.6 + 0.3,
                originalSize: 0,
                vx: 0, // Velocity for smooth movement
                vy: 0
            });
        }
    }
    
    bindEvents() {
        window.addEventListener('resize', () => {
            this.resize();
        });
        
        this.canvas.addEventListener('mousemove', (e) => {
            const rect = this.canvas.getBoundingClientRect();
            this.mouse.x = e.clientX - rect.left;
            this.mouse.y = e.clientY - rect.top;
        });
        
        this.canvas.addEventListener('mouseleave', () => {
            this.mouse.x = undefined;
            this.mouse.y = undefined;
        });
        
        this.canvas.addEventListener('touchmove', (e) => {
            e.preventDefault();
            const rect = this.canvas.getBoundingClientRect();
            const touch = e.touches[0];
            this.mouse.x = touch.clientX - rect.left;
            this.mouse.y = touch.clientY - rect.top;
        }, { passive: false });
        
        this.canvas.addEventListener('touchend', () => {
            this.mouse.x = undefined;
            this.mouse.y = undefined;
        });
        
        // Клик для создания волны
        this.canvas.addEventListener('click', (e) => {
            const rect = this.canvas.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            this.createWave(x, y);
        });
        
        this.canvas.addEventListener('touchstart', (e) => {
            e.preventDefault();
            const rect = this.canvas.getBoundingClientRect();
            const touch = e.touches[0];
            const x = touch.clientX - rect.left;
            const y = touch.clientY - rect.top;
            this.createWave(x, y);
        }, { passive: false });
    }
    
    createWave(x, y) {
        // Создаем волновой эффект при клике
        this.particles.forEach(particle => {
            const dx = particle.x - x;
            const dy = particle.y - y;
            const distance = Math.sqrt(dx * dx + dy * dy);
            
            if (distance < 200) {
                const force = (200 - distance) / 200;
                const angle = Math.atan2(dy, dx);
                
                particle.vx += Math.cos(angle) * force * 15;
                particle.vy += Math.sin(angle) * force * 15;
            }
        });
    }
    
    animate() {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        // Обновление и отрисовка частиц
        this.particles.forEach(particle => {
            this.updateParticle(particle);
            this.drawParticle(particle);
        });
        
        // Соединение частиц линиями (паутинка)
        this.connectParticles();
        
        requestAnimationFrame(() => this.animate());
    }
    
    updateParticle(particle) {
        // Плавное движение
        particle.vx *= 0.95;
        particle.vy *= 0.95;
        
        particle.x += particle.vx + particle.speedX * 0.1;
        particle.y += particle.vy + particle.speedY * 0.1;
        
        // Отскок от границ с затуханием
        if (particle.x < 0 || particle.x > this.canvas.width) {
            particle.vx *= -0.8;
            particle.x = Math.max(0, Math.min(this.canvas.width, particle.x));
        }
        if (particle.y < 0 || particle.y > this.canvas.height) {
            particle.vy *= -0.8;
            particle.y = Math.max(0, Math.min(this.canvas.height, particle.y));
        }
        
        // Взаимодействие с мышью
        if (this.mouse.x !== undefined && this.mouse.y !== undefined) {
            const dx = particle.x - this.mouse.x;
            const dy = particle.y - this.mouse.y;
            const distance = Math.sqrt(dx * dx + dy * dy);
            
            if (distance < this.mouse.radius) {
                const angle = Math.atan2(dy, dx);
                const force = (this.mouse.radius - distance) / this.mouse.radius;
                
                // Отталкивание от курсора
                particle.vx += Math.cos(angle) * force * this.interactionStrength * 0.5;
                particle.vy += Math.sin(angle) * force * this.interactionStrength * 0.5;
                
                // Увеличиваем размер при близости к курсору
                if (!particle.originalSize) {
                    particle.originalSize = particle.size;
                }
                particle.size = particle.originalSize * (1 + force);
            } else if (particle.originalSize) {
                particle.size += (particle.originalSize - particle.size) * 0.1;
            }
        }
        
        // Плавное возвращение к исходному размеру
        if (particle.originalSize && Math.abs(particle.size - particle.originalSize) > 0.01) {
            particle.size += (particle.originalSize - particle.size) * 0.1;
        }
    }
    
    drawParticle(particle) {
        // Градиент для частиц
        const gradient = this.ctx.createRadialGradient(
            particle.x, particle.y, 0,
            particle.x, particle.y, particle.size
        );
        gradient.addColorStop(0, particle.color.replace(')', ', 1)').replace('hsl', 'hsla'));
        gradient.addColorStop(1, particle.color.replace(')', ', 0.2)').replace('hsl', 'hsla'));
        
        this.ctx.beginPath();
        this.ctx.arc(particle.x, particle.y, particle.size, 0, Math.PI * 2);
        this.ctx.fillStyle = gradient;
        this.ctx.fill();
    }
    
    connectParticles() {
        this.ctx.strokeStyle = 'rgba(139, 92, 246, 0.1)';
        this.ctx.lineWidth = 0.8;
        
        for (let i = 0; i < this.particles.length; i++) {
            for (let j = i + 1; j < this.particles.length; j++) {
                const p1 = this.particles[i];
                const p2 = this.particles[j];
                
                const dx = p1.x - p2.x;
                const dy = p1.y - p2.y;
                const distance = Math.sqrt(dx * dx + dy * dy);
                
                if (distance < this.connectionDistance) {
                    // Прозрачность линии зависит от расстояния
                    const opacity = 0.3 * (1 - distance / this.connectionDistance);
                    this.ctx.strokeStyle = `rgba(139, 92, 246, ${opacity})`;
                    
                    this.ctx.beginPath();
                    this.ctx.moveTo(p1.x, p1.y);
                    this.ctx.lineTo(p2.x, p2.y);
                    this.ctx.stroke();
                }
            }
        }
    }
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    const canvas = document.getElementById('particlesCanvas');
    if (canvas) {
        // Задержка для улучшения производительности
        setTimeout(() => {
            new ParticleSystem(canvas);
        }, 1000);
    }
});

// Оптимизация для мобильных устройств
if ('ontouchstart' in window) {
    document.body.classList.add('touch-device');
}