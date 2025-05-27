import React, { useState } from 'react';

const LandingPage = ({ onLogin }) => {
  const [email, setEmail] = useState('');
  const [accessCode, setAccessCode] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');

    try {
      const response = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email: email.trim(),
          access_code: accessCode.trim()
        }),
      });

      const data = await response.json();

      if (response.ok) {
        // Store token in localStorage
        localStorage.setItem('access_token', data.access_token);
        localStorage.setItem('user_email', data.email);
        localStorage.setItem('access_level', data.access_level);
        
        // Call onLogin callback
        onLogin(data);
      } else {
        setError(data.detail || 'Login fejlede. Tjek din email og adgangskode.');
      }
    } catch (error) {
      console.error('Login error:', error);
      setError('Netværksfejl. Prøv igen.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50">
      {/* Header */}
      <header className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <div className="text-3xl">🏪</div>
              <div>
                <h1 className="text-2xl font-bold text-gray-900">Vapi AI Dashboard</h1>
                <p className="text-sm text-gray-600">Kundeindsigter fra supermarkeder</p>
              </div>
            </div>
            <div className="text-sm text-gray-500">
              Powered by Vapi AI
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="lg:grid lg:grid-cols-2 lg:gap-16 items-center">
          {/* Left Side - Information */}
          <div className="mb-12 lg:mb-0">
            <h2 className="text-4xl font-bold text-gray-900 mb-6">
              Real-time Customer Insights
            </h2>
            <p className="text-xl text-gray-600 mb-8">
              Få dybdegående indsigt i dine kunders oplevelser gennem AI-drevne interviews og sentiment analyse.
            </p>
            
            <div className="space-y-6">
              <div className="flex items-start space-x-4">
                <div className="flex-shrink-0">
                  <div className="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center">
                    <span className="text-blue-600 text-lg">🎯</span>
                  </div>
                </div>
                <div>
                  <h3 className="font-semibold text-gray-900">Theme Collector</h3>
                  <p className="text-gray-600">Automatisk opdagelse af temaer med sentiment analyse</p>
                </div>
              </div>
              
              <div className="flex items-start space-x-4">
                <div className="flex-shrink-0">
                  <div className="w-8 h-8 bg-green-100 rounded-full flex items-center justify-center">
                    <span className="text-green-600 text-lg">📊</span>
                  </div>
                </div>
                <div>
                  <h3 className="font-semibold text-gray-900">Real-time Analytics</h3>
                  <p className="text-gray-600">Live data fra Vapi AI interviews</p>
                </div>
              </div>
              
              <div className="flex items-start space-x-4">
                <div className="flex-shrink-0">
                  <div className="w-8 h-8 bg-purple-100 rounded-full flex items-center justify-center">
                    <span className="text-purple-600 text-lg">💬</span>
                  </div>
                </div>
                <div>
                  <h3 className="font-semibold text-gray-900">Intelligent Chat</h3>
                  <p className="text-gray-600">Stil spørgsmål til din data på dansk</p>
                </div>
              </div>
            </div>
          </div>

          {/* Right Side - Login Form */}
          <div className="bg-white rounded-2xl shadow-xl p-8">
            <div className="text-center mb-8">
              <h3 className="text-2xl font-bold text-gray-900 mb-2">Få Adgang</h3>
              <p className="text-gray-600">Indtast din email og adgangskode for at fortsætte</p>
            </div>

            {error && (
              <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
                <div className="flex items-center space-x-2">
                  <span className="text-red-500">⚠️</span>
                  <span className="text-red-700 text-sm">{error}</span>
                </div>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-6">
              <div>
                <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-2">
                  Email adresse
                </label>
                <input
                  type="email"
                  id="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="din@email.dk"
                  required
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors"
                />
              </div>

              <div>
                <label htmlFor="accessCode" className="block text-sm font-medium text-gray-700 mb-2">
                  Adgangskode
                </label>
                <input
                  type="text"
                  id="accessCode"
                  value={accessCode}
                  onChange={(e) => setAccessCode(e.target.value)}
                  placeholder="Indtast din adgangskode"
                  required
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors"
                />
              </div>

              <button
                type="submit"
                disabled={isLoading || !email || !accessCode}
                className="w-full bg-blue-600 text-white py-3 px-4 rounded-lg font-medium hover:bg-blue-700 focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {isLoading ? (
                  <div className="flex items-center justify-center space-x-2">
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                    <span>Logger ind...</span>
                  </div>
                ) : (
                  'Få Adgang til Dashboard'
                )}
              </button>
            </form>

            <div className="mt-8 pt-6 border-t border-gray-200">
              <div className="text-center">
                <p className="text-sm text-gray-500">Har du ikke en adgangskode?</p>
                <p className="text-sm text-gray-600 mt-2">Kontakt din administrator for at få adgang til dashboardet.</p>
              </div>
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="bg-gray-50 border-t">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="text-center text-sm text-gray-500">
            <p>© 2024 Vapi AI Dashboard - Sikret adgang til supermarked indsigter</p>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default LandingPage;
