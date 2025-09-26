class ParticleSystem {
    constructor(canvas) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        this.particles = [];
        this.mouse = { x: 0, y: 0, radius: 150 };
        this.interactionStrength = 5;
        
        this.init();
        this.animate();
        this.bindEvents();
    }
    
    init() {
        this.resize();
        this.createParticles(80);
    }
    
    resize() {
        this.canvas.width = window.innerWidth;
        this.canvas.height = window.innerHeight;
    }
    
    createParticles(count) {
        const colors = [
            'hsl(250, 70%, 60%)', // Purple
            'hsl(180, 100%, 50%)', // Cyan
            'hsl(300, 100%, 50%)', // Pink
            'hsl(120, 100%, 50%)'  // Green
        ];
        
        for (let i = 0; i < count; i++) {
            this.particles.push({
                x: Math.random() * this.canvas.width,
                y: Math.random() * this.canvas.height,
                size: Math.random() * 4 + 1,
                speedX: Math.random() * 2 - 1,
                speedY: Math.random() * 2 - 1,
                color: colors[Math.floor(Math.random() * colors.length)],
                opacity: Math.random() * 0.6 + 0.2,
                originalSize: 0
            });
        }
    }
    
    bindEvents() {
        window.addEventListener('resize', () => {
            this.resize();
            // Пересоздаем частицы при изменении размера окна
            this.particles = [];
            this.createParticles(80);
        });
        
        this.canvas.addEventListener('mousemove', (e) => {
            this.mouse.x = e.clientX;
            this.mouse.y = e.clientY;
        });
        
        this.canvas.addEventListener('mouseleave', () => {
            this.mouse.x = undefined;
            this.mouse.y = undefined;
        });
        
        this.canvas.addEventListener('click', (e) => {
            // Создаем взрыв частиц при клике
            this.createExplosion(e.clientX, e.clientY);
        });
    }
    
    createExplosion(x, y) {
        for (let i = 0; i < 10; i++) {
            this.particles.push({
                x: x,
                y: y,
                size: Math.random() * 3 + 1,
                speedX: (Math.random() - 0.5) * 10,
                speedY: (Math.random() - 0.5) * 10,
                color: 'hsl(' + (Math.random() * 60 + 250) + ', 70%, 60%)',
                opacity: 1,
                life: 1.0,
                decaying: true
            });
        }
    }
    
    animate() {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        // Обновление и отрисовка частиц
        for (let i = 0; i < this.particles.length; i++) {
            const particle = this.particles[i];
            
            // Уменьшение жизни для взрывных частиц
            if (particle.decaying) {
                particle.life -= 0.02;
                if (particle.life <= 0) {
                    this.particles.splice(i, 1);
                    i--;
                    continue;
                }
            }
            
            // Движение
            particle.x += particle.speedX;
            particle.y += particle.speedY;
            
            // Отскок от границ
            if (particle.x < 0 || particle.x > this.canvas.width) {
                particle.speedX *= -1;
                particle.x = Math.max(0, Math.min(this.canvas.width, particle.x));
            }
            if (particle.y < 0 || particle.y > this.canvas.height) {
                particle.speedY *= -1;
                particle.y = Math.max(0, Math.min(this.canvas.height, particle.y));
            }
            
            // Замедление
            if (!particle.decaying) {
                particle.speedX *= 0.99;
                particle.speedY *= 0.99;
            }
            
            // Взаимодействие с мышью
            if (this.mouse.x && this.mouse.y) {
                const dx = particle.x - this.mouse.x;
                const dy = particle.y - this.mouse.y;
                const distance = Math.sqrt(dx * dx + dy * dy);
                
                if (distance < this.mouse.radius) {
                    const angle = Math.atan2(dy, dx);
                    const force = (this.mouse.radius - distance) / this.mouse.radius;
                    
                    particle.x += Math.cos(angle) * force * this.interactionStrength;
                    particle.y += Math.sin(angle) * force * this.interactionStrength;
                    
                    // Увеличиваем размер при близости к курсору
                    if (!particle.originalSize) {
                        particle.originalSize = particle.size;
                    }
                    particle.size = particle.originalSize * (1 + force * 2);
                } else if (particle.originalSize) {
                    particle.size = particle.originalSize;
                }
            }
            
            // Отрисовка
            this.ctx.beginPath();
            this.ctx.arc(particle.x, particle.y, particle.size, 0, Math.PI * 2);
            
            if (particle.decaying) {
                this.ctx.fillStyle = particle.color.replace(')', `, ${particle.life})`).replace('hsl', 'hsla');
            } else {
                this.ctx.fillStyle = particle.color;
            }
            
            this.ctx.globalAlpha = particle.opacity * (particle.decaying ? particle.life : 1);
            this.ctx.fill();
        }
        
        // Соединение частиц линиями
        this.connectParticles();
        
        this.ctx.globalAlpha = 1;
        requestAnimationFrame(() => this.animate());
    }
    
    connectParticles() {
        for (let i = 0; i < this.particles.length; i++) {
            for (let j = i + 1; j < this.particles.length; j++) {
                const dx = this.particles[i].x - this.particles[j].x;
                const dy = this.particles[i].y - this.particles[j].y;
                const distance = Math.sqrt(dx * dx + dy * dy);
                
                if (distance < 120) {
                    const opacity = 0.2 * (1 - distance / 120);
                    
                    this.ctx.beginPath();
                    this.ctx.strokeStyle = `rgba(139, 92, 246, ${opacity})`;
                    this.ctx.lineWidth = 0.8;
                    this.ctx.moveTo(this.particles[i].x, this.particles[i].y);
                    this.ctx.lineTo(this.particles[j].x, this.particles[j].y);
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
        new ParticleSystem(canvas);
    }
});