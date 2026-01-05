console.log('🚀 Rust 静态文件服务已启动！');

// 页面加载完成后执行
document.addEventListener('DOMContentLoaded', function () {
    console.log('📄 页面加载完成');

    // 动态添加一些交互效果
    const container = document.querySelector('.container');
    if (container) {
        container.addEventListener('mouseenter', function () {
            this.style.transform = 'scale(1.02)';
            this.style.transition = 'transform 0.3s ease';
        });

        container.addEventListener('mouseleave', function () {
            this.style.transform = 'scale(1)';
        });
    }

    // 显示当前时间
    const now = new Date();
    console.log('🕐 当前时间:', now.toLocaleString('zh-CN'));
});

// 简单的交互功能
function showNotification(message) {
    const notification = document.createElement('div');
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: #667eea;
        color: white;
        padding: 15px 20px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        z-index: 1000;
        animation: slideIn 0.3s ease;
    `;

    document.body.appendChild(notification);

    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// 添加 CSS 动画
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    @keyframes slideOut {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(100%); opacity: 0; }
    }
`;
document.head.appendChild(style);

// 欢迎消息
setTimeout(() => {
    showNotification('欢迎访问 Rust 静态文件服务！');
}, 1000);