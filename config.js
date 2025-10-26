// config.js
// URL BASE DA API (Deploy no Render)
const API_BASE_URL = 'https://nexus-backend-pvj4.onrender.com';

// Função para obter o token de autenticação (se necessário no futuro)
function getAuthHeaders() {
    const token = localStorage.getItem('token');
    return {
        'Content-Type': 'application/json',
        // Adicione o token se o seu backend for exigir autenticação JWT
        // 'Authorization': token ? `Bearer ${token}` : ''
    };
}