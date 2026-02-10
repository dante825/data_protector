// Project Protector - Authentication JavaScript

// Password Strength Calculator
function calculatePasswordStrength(password) {
    let score = 0;
    const requirements = {
        length: password.length >= 8,
        uppercase: /[A-Z]/.test(password),
        lowercase: /[a-z]/.test(password),
        number: /[0-9]/.test(password),
        special: /[^A-Za-z0-9]/.test(password)
    };

    if (requirements.length) score++;
    if (requirements.uppercase) score++;
    if (requirements.lowercase) score++;
    if (requirements.number) score++;
    if (requirements.special) score++;

    return { score, requirements };
}

function updatePasswordStrength(password) {
    const strength = calculatePasswordStrength(password);
    const strengthMeter = document.getElementById('strength-meter');
    const strengthText = document.getElementById('strength-text');
    const reqLength = document.getElementById('req-length');
    const reqUppercase = document.getElementById('req-uppercase');
    const reqLowercase = document.getElementById('req-lowercase');
    const reqNumber = document.getElementById('req-number');
    const reqSpecial = document.getElementById('req-special');

    // Update meter
    strengthMeter.className = 'password-strength-meter';
    if (strength.score === 0) {
        strengthMeter.classList.add('weak');
        strengthText.textContent = '-';
    } else if (strength.score <= 2) {
        strengthMeter.classList.add('weak');
        strengthText.textContent = 'Weak';
    } else if (strength.score <= 4) {
        strengthMeter.classList.add('medium');
        strengthText.textContent = 'Medium';
    } else {
        strengthMeter.classList.add('strong');
        strengthText.textContent = 'Strong';
    }

    // Update requirements
    reqLength.className = strength.requirements.length ? 'met' : 'not-met';
    reqUppercase.className = strength.requirements.uppercase ? 'met' : 'not-met';
    reqLowercase.className = strength.requirements.lowercase ? 'met' : 'not-met';
    reqNumber.className = strength.requirements.number ? 'met' : 'not-met';
    reqSpecial.className = strength.requirements.special ? 'met' : 'not-met';

    return strength.score >= 5;
}

// Toggle Password Visibility
function togglePasswordVisibility(inputId, iconId) {
    const input = document.getElementById(inputId);
    const icon = document.getElementById(iconId);
    
    if (input.type === 'password') {
        input.type = 'text';
        icon.classList.remove('fa-eye');
        icon.classList.add('fa-eye-slash');
    } else {
        input.type = 'password';
        icon.classList.remove('fa-eye-slash');
        icon.classList.add('fa-eye');
    }
}

// Show Error Message
function showError(message) {
    const errorDiv = document.getElementById('error-message');
    errorDiv.innerHTML = `<i class="fas fa-exclamation-circle"></i> ${message}`;
    errorDiv.classList.add('visible');
    
    // Auto-hide after 5 seconds
    setTimeout(() => {
        errorDiv.classList.remove('visible');
    }, 5000);
}

// Show Success Message
function showSuccess(message) {
    const successDiv = document.getElementById('success-message');
    successDiv.innerHTML = `<i class="fas fa-check-circle"></i> ${message}`;
    successDiv.classList.add('visible');
    
    // Auto-hide after 5 seconds
    setTimeout(() => {
        successDiv.classList.remove('visible');
    }, 5000);
}

// Clear Messages
function clearMessages() {
    document.getElementById('error-message').classList.remove('visible');
    document.getElementById('success-message').classList.remove('visible');
}

// Token Management
function saveTokens(accessToken, refreshToken) {
    // Use sessionStorage as specified
    sessionStorage.setItem('accessToken', accessToken);
    sessionStorage.setItem('refreshToken', refreshToken);
    
    // Also store in localStorage for persistence (optional)
    localStorage.setItem('accessToken', accessToken);
    localStorage.setItem('refreshToken', refreshToken);
    
    // Store session start time
    sessionStorage.setItem('tokenStartTime', Date.now().toString());
}

function getAccessToken() {
    // Try sessionStorage first, then localStorage
    return sessionStorage.getItem('accessToken') || localStorage.getItem('accessToken');
}

function getRefreshToken() {
    return sessionStorage.getItem('refreshToken') || localStorage.getItem('refreshToken');
}

function clearTokens() {
    sessionStorage.removeItem('accessToken');
    sessionStorage.removeItem('refreshToken');
    localStorage.removeItem('accessToken');
    localStorage.removeItem('refreshToken');
}

function isTokenExpired() {
    const startTime = sessionStorage.getItem('tokenStartTime');
    if (!startTime) return true;
    
    const elapsed = Date.now() - parseInt(startTime);
    const tokenLifetime = 24 * 60 * 60 * 1000; // 24 hours in milliseconds
    
    return elapsed > tokenLifetime;
}

function getAuthHeaders() {
    const token = getAccessToken();
    if (!token) return {};
    return { 'Authorization': `Bearer ${token}` };
}

// Login Handler
function handleLogin(event) {
    event.preventDefault();
    
    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value;
    const rememberMe = document.getElementById('remember-me').checked;
    
    clearMessages();
    
    if (!username || !password) {
        showError('Please fill in all required fields');
        return;
    }
    
    const loginBtn = document.getElementById('login-btn');
    loginBtn.disabled = true;
    loginBtn.innerHTML = '<i class="fas fa-spin fa-circle-notch"></i> Logging in...';
    
    fetch('/api/auth/login', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded'
        },
        body: new URLSearchParams({
            'grant_type': '',
            'username': username,
            'password': password,
            'scope': '',
            'client_id': '',
            'client_secret': ''
        })
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(data => {
                throw new Error(data.detail || 'Login failed');
            });
        }
        return response.json();
    })
    .then(data => {
        saveTokens(data.access_token, data.refresh_token);
        showSuccess('Login successful! Redirecting...');
        
        setTimeout(() => {
            // If remember me checked, use localStorage
            if (rememberMe) {
                localStorage.setItem('accessToken', data.access_token);
            }
            // Redirect to main page
            window.location.href = '/';
        }, 1500);
    })
    .catch(error => {
        showError(error.message || 'Login failed. Please try again.');
    })
    .finally(() => {
        loginBtn.disabled = false;
        loginBtn.innerHTML = '<i class="fas fa-sign-in-alt"></i> Login';
    });
}

// Register Handler
function handleRegister(event) {
    event.preventDefault();
    
    const username = document.getElementById('username').value.trim();
    const email = document.getElementById('email').value.trim();
    const fullName = document.getElementById('full_name').value.trim();
    const password = document.getElementById('password').value;
    const confirmPassword = document.getElementById('confirm_password').value;
    const termsChecked = document.getElementById('terms-checkbox').checked;
    
    clearMessages();
    
    // Basic validation
    if (!username || !email || !password) {
        showError('Please fill in all required fields');
        return;
    }
    
    if (username.length < 3 || username.length > 50) {
        showError('Username must be between 3 and 50 characters');
        return;
    }
    
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
        showError('Please enter a valid email address');
        return;
    }
    
    if (password !== confirmPassword) {
        showError('Passwords do not match');
        return;
    }
    
    if (!termsChecked) {
        showError('You must agree to the terms of service');
        return;
    }
    
    // Check password strength
    const strength = calculatePasswordStrength(password);
    if (strength.score < 5) {
        showError('Password does not meet all requirements. Please use a stronger password.');
        return;
    }
    
    const registerBtn = document.getElementById('register-btn');
    registerBtn.disabled = true;
    registerBtn.innerHTML = '<i class="fas fa-user-plus"></i> Creating account...';
    
    fetch('/api/auth/register', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            username: username,
            email: email,
            full_name: fullName || null,
            password: password
        })
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(data => {
                throw new Error(data.detail || 'Registration failed');
            });
        }
        return response.json();
    })
    .then(data => {
        showSuccess(`Registration successful! Welcome, ${data.username}. You can now login.`);
        
        setTimeout(() => {
            window.location.href = '/login';
        }, 2000);
    })
    .catch(error => {
        showError(error.message || 'Registration failed. Please try again.');
    })
    .finally(() => {
        registerBtn.disabled = false;
        registerBtn.innerHTML = '<i class="fas fa-user-plus"></i> Register Account';
    });
}

// Logout Handler
function handleLogout() {
    const token = getAccessToken();
    
    fetch('/api/auth/logout', {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${token}`
        }
    })
    .then(() => {
        clearTokens();
        showSuccess('Logged out successfully');
        window.location.href = '/login';
    })
    .catch(() => {
        clearTokens();
        window.location.href = '/login';
    });
}

// Token Refresh
async function refreshAccessToken() {
    const refreshToken = getRefreshToken();
    if (!refreshToken) return null;
    
    try {
        const response = await fetch('/api/auth/refresh-token', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ refresh_token: refreshToken })
        });
        
        if (!response.ok) {
            throw new Error('Token refresh failed');
        }
        
        const data = await response.json();
        saveTokens(data.access_token, data.refresh_token);
        return data.access_token;
    } catch (error) {
        clearTokens();
        throw error;
    }
}

// Check Authentication Status
function checkAuthStatus() {
    const token = getAccessToken();
    
    if (!token || isTokenExpired()) {
        // Try to refresh
        return refreshAccessToken()
            .then(() => {
                return true; // Still authenticated
            })
            .catch(() => {
                // Not authenticated
                if (window.location.pathname !== '/login' && window.location.pathname !== '/register') {
                    window.location.href = '/login';
                }
                return false;
            });
    }
    
    return Promise.resolve(true);
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    // Login form
    const loginForm = document.getElementById('login-form');
    if (loginForm) {
        loginForm.addEventListener('submit', handleLogin);
    }
    
    // Register form
    const registerForm = document.getElementById('register-form');
    if (registerForm) {
        // Real-time password strength check
        const passwordInput = document.getElementById('password');
        if (passwordInput) {
            passwordInput.addEventListener('input', () => {
                updatePasswordStrength(passwordInput.value);
            });
        }
        
        // Password match validation
        const confirmPasswordInput = document.getElementById('confirm_password');
        if (confirmPasswordInput) {
            confirmPasswordInput.addEventListener('input', () => {
                const password = document.getElementById('password').value;
                const confirmPassword = confirmPasswordInput.value;
                const matchMessage = document.getElementById('password-match-message');
                
                if (password && confirmPassword) {
                    if (password === confirmPassword) {
                        matchMessage.style.display = 'none';
                        confirmPasswordInput.style.borderColor = '#28a745';
                    } else {
                        matchMessage.style.display = 'block';
                        confirmPasswordInput.style.borderColor = '#dc3545';
                    }
                } else {
                    matchMessage.style.display = 'none';
                    confirmPasswordInput.style.borderColor = '#dee2e6';
                }
            });
        }
        
        // Enable register button only when all validations pass
        const registerBtn = document.getElementById('register-btn');
        if (registerBtn) {
            const validateRegister = () => {
                const password = document.getElementById('password').value;
                const confirmPassword = document.getElementById('confirm_password').value;
                const termsChecked = document.getElementById('terms-checkbox').checked;
                const strength = calculatePasswordStrength(password);
                
                registerBtn.disabled = !(strength.score >= 5 && password === confirmPassword && termsChecked);
            };
            
            document.getElementById('confirm_password').addEventListener('input', validateRegister);
            document.getElementById('terms-checkbox').addEventListener('change', validateRegister);
        }
        
        registerForm.addEventListener('submit', handleRegister);
    }
    
    // Password visibility toggles
    document.getElementById('toggle-password')?.addEventListener('click', () => {
        togglePasswordVisibility('password', 'toggle-password');
    });
    
    document.getElementById('toggle-confirm-password')?.addEventListener('click', () => {
        togglePasswordVisibility('confirm_password', 'toggle-confirm-password');
    });
    
    // Logout link
    const logoutLink = document.getElementById('logout-link');
    if (logoutLink) {
        logoutLink.addEventListener('click', (e) => {
            e.preventDefault();
            handleLogout();
        });
    }
    
    // Check auth status on page load for protected pages
    if (window.location.pathname === '/' || window.location.pathname.startsWith('/api/')) {
        checkAuthStatus();
    }
});
