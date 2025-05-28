import React, { useState, useEffect, useCallback } from 'react';
import './App.css';
import LandingPage from './LandingPage';

const API_BASE_URL = process.env.REACT_APP_BACKEND_URL;

// Error Boundary Component
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('Dashboard Error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-red-50 flex items-center justify-center">
          <div className="bg-white p-8 rounded-xl shadow-lg max-w-md text-center">
            <div className="text-red-500 text-6xl mb-4">⚠️</div>
            <h2 className="text-xl font-bold text-gray-800 mb-2">Dashboard Fejl</h2>
            <p className="text-gray-600 mb-4">Der opstod en uventet fejl. Prøv at genindlæse siden.</p>
            <button 
              onClick={() => window.location.reload()}
              className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600"
            >
              Genindlæs
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

// Auth utility functions
const getStoredToken = () => localStorage.getItem('access_token');
const getStoredUser = () => ({
  email: localStorage.getItem('user_email'),
  accessLevel: localStorage.getItem('access_level')
});

const clearStoredAuth = () => {
  localStorage.removeItem('access_token');
  localStorage.removeItem('user_email');
  localStorage.removeItem('access_level');
};

// API utility functions
const apiCall = async (endpoint, options = {}) => {
  try {
    const token = getStoredToken();
    console.log(`Making API call to: ${API_BASE_URL}/api/${endpoint}`);
    
    const response = await fetch(`${API_BASE_URL}/api/${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(token && { 'Authorization': `Bearer ${token}` }),
        ...options.headers,
      },
    });

    console.log(`API response for ${endpoint}:`, response.status, response.statusText);

    if (response.status === 401) {
      // Token expired or invalid
      clearStoredAuth();
      window.location.reload();
      return;
    }

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`API Error: ${response.status} - ${response.statusText} - ${errorText}`);
    }

    const data = await response.json();
    console.log(`API data for ${endpoint}:`, data);
    return data;
  } catch (error) {
    console.error(`API call failed for ${endpoint}:`, error);
    throw error;
  }
};

// Loading Component
const LoadingSpinner = ({ message = "Indlæser..." }) => (
  <div className="flex items-center justify-center space-x-3">
    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
    <span className="text-gray-600">{message}</span>
  </div>
);

// Error Message Component
const ErrorMessage = ({ message, onRetry }) => (
  <div className="bg-red-50 border border-red-200 rounded-lg p-4">
    <div className="flex items-center space-x-3">
      <div className="text-red-500">⚠️</div>
      <div className="flex-1">
        <h3 className="text-red-800 font-medium">Fejl</h3>
        <p className="text-red-600 text-sm">{message}</p>
      </div>
      {onRetry && (
        <button 
          onClick={onRetry}
          className="px-3 py-1 bg-red-500 text-white text-sm rounded hover:bg-red-600"
        >
          Prøv igen
        </button>
      )}
    </div>
  </div>
);

// Enhanced Interview Reader Widget - With editing capabilities
const EnhancedInterviewReaderWidget = ({ interviews, isLoading, user }) => {
  const [selectedInterview, setSelectedInterview] = useState(null);
  const [fullTranscript, setFullTranscript] = useState(null);
  const [loadingTranscript, setLoadingTranscript] = useState(false);
  const [filter, setFilter] = useState('');
  const [editingSegment, setEditingSegment] = useState(null);
  const [editText, setEditText] = useState('');
  const [availableThemes, setAvailableThemes] = useState([]);

  const isEditable = user?.accessLevel?.includes('Premium') || user?.accessLevel?.includes('Admin');

  // Fetch available themes on mount
  useEffect(() => {
    const fetchThemes = async () => {
      try {
        const data = await apiCall('themes/available');
        setAvailableThemes(data.themes || []);
      } catch (error) {
        console.error('Error fetching themes:', error);
      }
    };
    fetchThemes();
  }, []);

  const fetchFullTranscript = async (interviewId) => {
    setLoadingTranscript(true);
    try {
      const data = await apiCall(`interview/${interviewId}`);
      setFullTranscript(data);
      setSelectedInterview(interviewId);
    } catch (error) {
      console.error('Error fetching full transcript:', error);
    } finally {
      setLoadingTranscript(false);
    }
  };

  const handleEditSegment = async (segmentId, newText) => {
    if (!isEditable) return;
    
    try {
      await apiCall('interview/edit', {
        method: 'POST',
        body: JSON.stringify({
          interview_id: selectedInterview,
          segment_id: segmentId,
          edited_text: newText
        })
      });
      
      // Refresh transcript
      await fetchFullTranscript(selectedInterview);
      setEditingSegment(null);
    } catch (error) {
      console.error('Error editing segment:', error);
    }
  };

  const handleTagSegment = async (segmentId, sentiment, theme, notes) => {
    if (!isEditable) return;
    
    try {
      await apiCall('interview/tag', {
        method: 'POST',
        body: JSON.stringify({
          interview_id: selectedInterview,
          segment_id: segmentId,
          sentiment,
          theme,
          notes
        })
      });
      
      // Refresh transcript
      await fetchFullTranscript(selectedInterview);
    } catch (error) {
      console.error('Error tagging segment:', error);
    }
  };

  const formatDuration = (seconds) => {
    if (!seconds || seconds === 0) return '0:00';
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
  };

  if (isLoading) {
    return (
      <div className="bg-white rounded-xl shadow-lg p-6">
        <div className="animate-pulse">
          <div className="h-6 bg-gray-200 rounded w-1/3 mb-4"></div>
          <div className="space-y-4">
            {[1, 2, 3].map(i => (
              <div key={i} className="h-16 bg-gray-200 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  const interviewsArray = Array.isArray(interviews) ? interviews : [];
  const filteredInterviews = interviewsArray.filter(interview => 
    (interview?.supermarket || '').toLowerCase().includes(filter.toLowerCase()) ||
    (interview?.transcript || '').toLowerCase().includes(filter.toLowerCase())
  );

  return (
    <div className="bg-white rounded-xl shadow-lg p-6">
      <div className="flex justify-between items-center mb-6">
        <div className="flex items-center space-x-4">
          <h2 className="text-2xl font-bold text-gray-800">📖 Interview Læser</h2>
          {isEditable && (
            <span className="px-3 py-1 bg-purple-100 text-purple-800 text-sm rounded-full font-medium">
              👑 Redigeringstilstand
            </span>
          )}
        </div>
        <input
          type="text"
          placeholder="Søg i interviews..."
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Interview List */}
        <div className="space-y-4">
          <h3 className="text-lg font-semibold text-gray-800 mb-4">Vælg Interview</h3>
          <div className="max-h-96 overflow-y-auto space-y-3">
            {filteredInterviews.length > 0 ? filteredInterviews.map((interview) => (
              <div 
                key={interview?.id || Math.random()} 
                className={`border rounded-lg p-4 cursor-pointer transition-all ${
                  selectedInterview === interview?.id 
                    ? 'border-blue-500 bg-blue-50' 
                    : 'border-gray-200 hover:border-gray-300 hover:shadow-md'
                }`}
                onClick={() => fetchFullTranscript(interview?.id)}
              >
                <div className="flex justify-between items-start mb-2">
                  <div className="flex items-center space-x-3">
                    <span className="font-medium text-gray-800">
                      {interview?.supermarket || 'Ukendt supermarked'}
                    </span>
                    <span className={`px-2 py-1 rounded-full text-xs ${
                      (interview?.status || 'unknown') === 'completed' 
                        ? 'bg-green-100 text-green-800' 
                        : 'bg-yellow-100 text-yellow-800'
                    }`}>
                      {(interview?.status || 'unknown') === 'completed' ? 'Gennemført' : 'Aktiv'}
                    </span>
                  </div>
                  <div className="text-sm text-gray-500">
                    {interview?.timestamp ? new Date(interview.timestamp).toLocaleDateString('da-DK') : 'Ukendt dato'}
                  </div>
                </div>
                <p className="text-sm text-gray-600 line-clamp-2">
                  {interview?.transcript ? (interview.transcript.substring(0, 100) + '...') : 'Ingen transskription'}
                </p>
                <div className="flex justify-between items-center mt-2">
                  <div className="text-sm text-gray-500">
                    <span className="font-medium text-blue-600">
                      Varighed: {formatDuration(interview?.duration)}
                    </span>
                  </div>
                  <div className="text-sm font-medium text-blue-600">
                    Samlet: {interview?.ratings?.samlet_karakter || 'N/A'}/10
                  </div>
                </div>
              </div>
            )) : (
              <div className="text-center text-gray-500 py-8">
                {filter ? 'Ingen interviews matcher søgningen' : 'Ingen interviews fundet'}
              </div>
            )}
          </div>
        </div>

        {/* Enhanced Transcript Display */}
        <div className="space-y-4">
          <h3 className="text-lg font-semibold text-gray-800 mb-4">Interview Transskription</h3>
          
          {loadingTranscript ? (
            <div className="flex items-center justify-center py-12">
              <LoadingSpinner message="Indlæser interview..." />
            </div>
          ) : fullTranscript ? (
            <div className="bg-gray-50 rounded-lg p-6">
              {/* Interview Header */}
              <div className="mb-4 pb-4 border-b border-gray-200">
                <div className="flex justify-between items-start mb-2">
                  <h4 className="text-lg font-semibold text-gray-800">
                    {fullTranscript.supermarket}
                  </h4>
                  <span className="text-sm text-gray-500">
                    {new Date(fullTranscript.timestamp).toLocaleString('da-DK')}
                  </span>
                </div>
                <div className="flex items-center space-x-4 text-sm text-gray-600">
                  <span className="font-medium text-blue-600">
                    Varighed: {formatDuration(fullTranscript.duration)}
                  </span>
                  <span>Status: {fullTranscript.status === 'completed' ? 'Gennemført' : 'Aktiv'}</span>
                  <span className="text-blue-600">🔒 Anonymiseret</span>
                  {fullTranscript.editable && (
                    <span className="text-purple-600">✏️ Redigerbar</span>
                  )}
                </div>
              </div>
              
              {/* Segmented Transcript */}
              <div className="max-h-96 overflow-y-auto space-y-4">
                {fullTranscript.segments && fullTranscript.segments.length > 0 ? (
                  fullTranscript.segments.map((segment, index) => (
                    <SegmentDisplay 
                      key={segment.id}
                      segment={segment}
                      isEditable={isEditable && segment.editable}
                      availableThemes={availableThemes}
                      onEdit={handleEditSegment}
                      onTag={handleTagSegment}
                      editingSegment={editingSegment}
                      setEditingSegment={setEditingSegment}
                      editText={editText}
                      setEditText={setEditText}
                    />
                  ))
                ) : (
                  <div className="prose prose-sm max-w-none">
                    <div className="whitespace-pre-wrap text-gray-700 leading-relaxed">
                      {fullTranscript.transcript}
                    </div>
                  </div>
                )}
              </div>
              
              {/* Ratings Summary */}
              {fullTranscript.ratings && (
                <div className="mt-4 pt-4 border-t border-gray-200">
                  <h5 className="font-medium text-gray-800 mb-2">Karakterer:</h5>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div>Udvalg: {fullTranscript.ratings.udvalg_af_varer}/10</div>
                    <div>Indretning: {fullTranscript.ratings.overskuelighed_indretning}/10</div>
                    <div>Personale: {fullTranscript.ratings.stemning_personal}/10</div>
                    <div>Priser: {fullTranscript.ratings.prisniveau_kvalitet}/10</div>
                    <div className="col-span-2 font-medium">
                      Samlet: {fullTranscript.ratings.samlet_karakter}/10
                    </div>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="bg-gray-50 rounded-lg p-12 text-center">
              <div className="text-gray-400 text-6xl mb-4">📖</div>
              <h4 className="text-lg font-medium text-gray-600 mb-2">Vælg et Interview</h4>
              <p className="text-gray-500">Klik på et interview til venstre for at læse det fulde anonymiserede referat</p>
              {isEditable && (
                <p className="text-purple-600 text-sm mt-2">✏️ Du kan redigere og tagge kundesvar</p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

// Segment Display Component for individual transcript segments
const SegmentDisplay = ({ 
  segment, 
  isEditable, 
  availableThemes, 
  onEdit, 
  onTag, 
  editingSegment, 
  setEditingSegment, 
  editText, 
  setEditText 
}) => {
  const [showTagging, setShowTagging] = useState(false);
  const [selectedSentiment, setSelectedSentiment] = useState(segment.tags?.sentiment || '');
  const [selectedTheme, setSelectedTheme] = useState(segment.tags?.theme || '');
  const [notes, setNotes] = useState(segment.tags?.notes || '');

  const getSentimentColor = (sentiment) => {
    switch (sentiment) {
      case 'positive': return 'bg-green-100 text-green-800';
      case 'negative': return 'bg-red-100 text-red-800';
      case 'neutral': return 'bg-yellow-100 text-yellow-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const startEdit = () => {
    setEditingSegment(segment.id);
    setEditText(segment.edited_text || segment.text);
  };

  const saveEdit = () => {
    onEdit(segment.id, editText);
  };

  const cancelEdit = () => {
    setEditingSegment(null);
    setEditText('');
  };

  const saveTags = () => {
    onTag(segment.id, selectedSentiment, selectedTheme, notes);
    setShowTagging(false);
  };

  return (
    <div className={`p-4 rounded-lg border ${
      segment.speaker === 'AI' 
        ? 'bg-blue-50 border-blue-200' 
        : 'bg-white border-gray-200'
    }`}>
      <div className="flex justify-between items-start mb-2">
        <span className={`text-xs font-medium px-2 py-1 rounded ${
          segment.speaker === 'AI' 
            ? 'bg-blue-100 text-blue-800' 
            : 'bg-green-100 text-green-800'
        }`}>
          {segment.speaker === 'AI' ? '🤖 AI' : '👤 Kunde'}
        </span>
        
        {isEditable && segment.editable && (
          <div className="flex space-x-2">
            {editingSegment === segment.id ? (
              <>
                <button 
                  onClick={saveEdit}
                  className="text-green-600 hover:text-green-800 text-sm"
                >
                  ✓ Gem
                </button>
                <button 
                  onClick={cancelEdit}
                  className="text-red-600 hover:text-red-800 text-sm"
                >
                  ✗ Annuller
                </button>
              </>
            ) : (
              <>
                <button 
                  onClick={startEdit}
                  className="text-blue-600 hover:text-blue-800 text-sm"
                >
                  ✏️ Rediger
                </button>
                <button 
                  onClick={() => setShowTagging(!showTagging)}
                  className="text-purple-600 hover:text-purple-800 text-sm"
                >
                  🏷️ Tag
                </button>
              </>
            )}
          </div>
        )}
      </div>
      
      {/* Segment Text */}
      {editingSegment === segment.id ? (
        <textarea 
          value={editText}
          onChange={(e) => setEditText(e.target.value)}
          className="w-full p-2 border border-gray-300 rounded resize-none"
          rows={3}
        />
      ) : (
        <p className="text-gray-700 leading-relaxed">
          {segment.edited_text || segment.text}
        </p>
      )}
      
      {/* Tags Display */}
      {segment.tags && (
        <div className="mt-2 flex flex-wrap gap-2">
          {segment.tags.sentiment && (
            <span className={`px-2 py-1 text-xs rounded ${getSentimentColor(segment.tags.sentiment)}`}>
              {segment.tags.sentiment}
            </span>
          )}
          {segment.tags.theme && (
            <span className="px-2 py-1 text-xs bg-blue-100 text-blue-800 rounded">
              {segment.tags.theme}
            </span>
          )}
          {segment.tags.notes && (
            <span className="px-2 py-1 text-xs bg-gray-100 text-gray-800 rounded">
              📝 {segment.tags.notes}
            </span>
          )}
        </div>
      )}
      
      {/* Tagging Interface */}
      {showTagging && isEditable && (
        <div className="mt-3 p-3 bg-gray-50 rounded border">
          <h6 className="font-medium text-gray-800 mb-2">Tilføj Tags</h6>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-600 mb-1">Sentiment</label>
              <select 
                value={selectedSentiment}
                onChange={(e) => setSelectedSentiment(e.target.value)}
                className="w-full text-sm border border-gray-300 rounded px-2 py-1"
              >
                <option value="">Vælg sentiment</option>
                <option value="positive">Positiv</option>
                <option value="neutral">Neutral</option>
                <option value="negative">Negativ</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-600 mb-1">Tema</label>
              <select 
                value={selectedTheme}
                onChange={(e) => setSelectedTheme(e.target.value)}
                className="w-full text-sm border border-gray-300 rounded px-2 py-1"
              >
                <option value="">Vælg tema</option>
                {availableThemes.map(theme => (
                  <option key={theme} value={theme}>{theme}</option>
                ))}
              </select>
            </div>
          </div>
          <div className="mt-2">
            <label className="block text-xs text-gray-600 mb-1">Noter</label>
            <input 
              type="text"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Tilføj noter..."
              className="w-full text-sm border border-gray-300 rounded px-2 py-1"
            />
          </div>
          <div className="mt-3 flex justify-end space-x-2">
            <button 
              onClick={() => setShowTagging(false)}
              className="px-3 py-1 text-sm text-gray-600 hover:text-gray-800"
            >
              Annuller
            </button>
            <button 
              onClick={saveTags}
              className="px-3 py-1 text-sm bg-blue-500 text-white rounded hover:bg-blue-600"
            >
              Gem Tags
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

// Theme Collector Component - The centerpiece widget
const ThemeCollectorWidget = ({ themes, isLoading }) => {
  const [expandedTheme, setExpandedTheme] = useState(null);
  const [selectedTimeRange, setSelectedTimeRange] = useState('7');

  const getSentimentColor = (sentiment) => {
    switch (sentiment) {
      case 'positive': return 'text-green-600 bg-green-100';
      case 'negative': return 'text-red-600 bg-red-100';
      default: return 'text-yellow-600 bg-yellow-100';
    }
  };

  const getSentimentIcon = (sentiment) => {
    switch (sentiment) {
      case 'positive': return '😊';
      case 'negative': return '😞';
      default: return '😐';
    }
  };

  if (isLoading) {
    return (
      <div className="bg-white rounded-xl shadow-lg p-6">
        <div className="animate-pulse">
          <div className="h-6 bg-gray-200 rounded w-1/3 mb-4"></div>
          <div className="space-y-4">
            {[1, 2, 3].map(i => (
              <div key={i} className="h-20 bg-gray-200 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  const themesArray = Array.isArray(themes) ? themes : [];

  return (
    <div className="bg-white rounded-xl shadow-lg p-6">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold text-gray-800 flex items-center">
          🎯 Theme Collector med Sentiment Analyse
        </h2>
        <select 
          value={selectedTimeRange}
          onChange={(e) => setSelectedTimeRange(e.target.value)}
          className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
        >
          <option value="1">I dag</option>
          <option value="7">Sidste 7 dage</option>
          <option value="30">Sidste 30 dage</option>
        </select>
      </div>

      <div className="space-y-4">
        {themesArray.length > 0 ? themesArray.map((theme, index) => (
          <div key={index} className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow">
            <div className="flex justify-between items-start mb-3">
              <div className="flex items-center space-x-3">
                <h3 className="text-lg font-semibold text-gray-800">{theme.name}</h3>
                {theme.is_new && (
                  <span className="px-2 py-1 bg-blue-500 text-white text-xs rounded-full font-bold">
                    NY
                  </span>
                )}
                <span className="text-sm text-gray-500">
                  {theme.total_mentions} nævninger
                </span>
              </div>
              <button 
                onClick={() => setExpandedTheme(expandedTheme === index ? null : index)}
                className="text-blue-500 hover:text-blue-700 font-medium"
              >
                {expandedTheme === index ? 'Skjul detaljer' : 'Vis detaljer'}
              </button>
            </div>

            {/* Sentiment Bar Chart */}
            <div className="mb-4">
              <div className="flex items-center space-x-2 text-sm text-gray-600 mb-2">
                <span>Sentiment fordeling:</span>
              </div>
              <div className="flex h-6 rounded-lg overflow-hidden bg-gray-100">
                <div 
                  className="bg-green-500 flex items-center justify-center text-white text-xs font-bold"
                  style={{ width: `${theme.total_mentions > 0 ? (theme.sentiment_breakdown.positive / theme.total_mentions) * 100 : 0}%` }}
                >
                  {theme.sentiment_breakdown.positive > 0 && theme.sentiment_breakdown.positive}
                </div>
                <div 
                  className="bg-yellow-500 flex items-center justify-center text-white text-xs font-bold"
                  style={{ width: `${theme.total_mentions > 0 ? (theme.sentiment_breakdown.neutral / theme.total_mentions) * 100 : 0}%` }}
                >
                  {theme.sentiment_breakdown.neutral > 0 && theme.sentiment_breakdown.neutral}
                </div>
                <div 
                  className="bg-red-500 flex items-center justify-center text-white text-xs font-bold"
                  style={{ width: `${theme.total_mentions > 0 ? (theme.sentiment_breakdown.negative / theme.total_mentions) * 100 : 0}%` }}
                >
                  {theme.sentiment_breakdown.negative > 0 && theme.sentiment_breakdown.negative}
                </div>
              </div>
              <div className="flex justify-between text-xs text-gray-500 mt-1">
                <span>😊 Positiv ({theme.sentiment_breakdown.positive})</span>
                <span>😐 Neutral ({theme.sentiment_breakdown.neutral})</span>
                <span>😞 Negativ ({theme.sentiment_breakdown.negative})</span>
              </div>
            </div>

            {/* Expanded Details */}
            {expandedTheme === index && (
              <div className="mt-4 border-t pt-4">
                {['positive', 'neutral', 'negative'].map(sentiment => (
                  theme.sample_quotes[sentiment]?.length > 0 && (
                    <div key={sentiment} className="mb-4">
                      <h4 className={`text-sm font-semibold mb-2 flex items-center ${getSentimentColor(sentiment)} px-2 py-1 rounded`}>
                        {getSentimentIcon(sentiment)} {sentiment === 'positive' ? 'Positive' : sentiment === 'neutral' ? 'Neutrale' : 'Negative'} citater
                      </h4>
                      <div className="space-y-2">
                        {theme.sample_quotes[sentiment].slice(0, 3).map((quote, idx) => (
                          <div key={idx} className="bg-gray-50 p-3 rounded border-l-4 border-gray-300">
                            <p className="text-sm text-gray-700 italic">"{quote.text}"</p>
                            <div className="text-xs text-gray-500 mt-1">
                              {new Date(quote.timestamp).toLocaleDateString('da-DK')} - {quote.supermarket}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )
                ))}
              </div>
            )}
          </div>
        )) : (
          <div className="text-center text-gray-500 py-8">
            Ingen temaer fundet endnu
          </div>
        )}
      </div>
    </div>
  );
};

// Overview Statistics Widget
const OverviewWidget = ({ overview, isLoading }) => {
  if (isLoading) {
    return (
      <div className="bg-white rounded-xl shadow-lg p-6">
        <div className="animate-pulse">
          <div className="h-6 bg-gray-200 rounded w-1/2 mb-4"></div>
          <div className="grid grid-cols-2 gap-4">
            {[1, 2, 3, 4].map(i => (
              <div key={i} className="h-16 bg-gray-200 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl shadow-lg p-6">
      <h2 className="text-2xl font-bold text-gray-800 mb-6 flex items-center">
        📊 Oversigt - {overview?.assistant_name || 'MindCalls Assistant'}
      </h2>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="text-center">
          <div className="text-3xl font-bold text-blue-600">{overview?.total_interviews || 0}</div>
          <div className="text-sm text-gray-600">Gennemførte interviews</div>
        </div>
        <div className="text-center">
          <div className="text-3xl font-bold text-green-600">{overview?.active_interviews || 0}</div>
          <div className="text-sm text-gray-600">Aktive interviews</div>
        </div>
        <div className="text-center">
          <div className="text-3xl font-bold text-purple-600">{overview?.avg_duration || 0}s</div>
          <div className="text-sm text-gray-600">Gennemsnitlig varighed</div>
        </div>
        <div className="text-center">
          <div className={`text-3xl font-bold ${(overview?.trend_percentage || 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {(overview?.trend_percentage || 0) >= 0 ? '+' : ''}{overview?.trend_percentage || 0}%
          </div>
          <div className="text-sm text-gray-600">Trend denne uge</div>
        </div>
      </div>
      {overview?.user_access_level && (
        <div className="mt-4 pt-4 border-t text-center">
          <span className="text-sm text-blue-600 bg-blue-50 px-3 py-1 rounded-full">
            {overview.user_access_level}
          </span>
        </div>
      )}
    </div>
  );
};

// Ratings Bar Chart Widget
const RatingsWidget = ({ ratings, isLoading }) => {
  if (isLoading) {
    return (
      <div className="bg-white rounded-xl shadow-lg p-6">
        <div className="animate-pulse">
          <div className="h-6 bg-gray-200 rounded w-1/3 mb-4"></div>
          <div className="space-y-4">
            {[1, 2, 3, 4, 5].map(i => (
              <div key={i} className="h-8 bg-gray-200 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  const ratingsArray = ratings ? Object.entries(ratings) : [];

  return (
    <div className="bg-white rounded-xl shadow-lg p-6">
      <h2 className="text-2xl font-bold text-gray-800 mb-6">📈 Standardkarakterer</h2>
      <div className="space-y-4">
        {ratingsArray.length > 0 ? ratingsArray.map(([key, data]) => (
          <div key={key} className="flex items-center space-x-4">
            <div className="w-1/3 text-sm font-medium text-gray-700">
              {data?.label || key}
            </div>
            <div className="flex-1 bg-gray-200 rounded-full h-8 relative">
              <div 
                className={`h-8 rounded-full flex items-center justify-end pr-3 text-white font-bold text-sm ${
                  (data?.color || 'gray') === 'green' ? 'bg-green-500' : 
                  (data?.color || 'gray') === 'yellow' ? 'bg-yellow-500' : 'bg-red-500'
                }`}
                style={{ width: `${((data?.average || 0) / 10) * 100}%` }}
              >
                {data?.average || 0}/10
              </div>
            </div>
          </div>
        )) : (
          <div className="text-center text-gray-500 py-8">
            Ingen ratings data tilgængelig endnu
          </div>
        )}
      </div>
    </div>
  );
};

// Overview Statistics Widget
const OverviewWidget = ({ overview, isLoading }) => {
  const [filter, setFilter] = useState('');

  if (isLoading) {
    return (
      <div className="bg-white rounded-xl shadow-lg p-6">
        <div className="animate-pulse">
          <div className="h-6 bg-gray-200 rounded w-1/3 mb-4"></div>
          <div className="space-y-4">
            {[1, 2, 3].map(i => (
              <div key={i} className="h-16 bg-gray-200 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  const interviewsArray = Array.isArray(interviews) ? interviews : [];
  const filteredInterviews = interviewsArray.filter(interview => 
    (interview?.supermarket || '').toLowerCase().includes(filter.toLowerCase()) ||
    (interview?.transcript || '').toLowerCase().includes(filter.toLowerCase())
  );

  return (
    <div className="bg-white rounded-xl shadow-lg p-6">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold text-gray-800">📝 Besvarelseslog</h2>
        <input
          type="text"
          placeholder="Filtrer interviews..."
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
        />
      </div>
      <div className="max-h-96 overflow-y-auto space-y-4">
        {filteredInterviews.length > 0 ? filteredInterviews.map((interview) => (
          <div key={interview?.id || Math.random()} className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow">
            <div className="flex justify-between items-start mb-2">
              <div className="flex items-center space-x-3">
                <span className="font-medium text-gray-800">{interview?.supermarket || 'Ukendt supermarked'}</span>
                <span className={`px-2 py-1 rounded-full text-xs ${
                  (interview?.status || 'unknown') === 'completed' ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'
                }`}>
                  {(interview?.status || 'unknown') === 'completed' ? 'Gennemført' : 'Aktiv'}
                </span>
              </div>
              <div className="text-sm text-gray-500">
                {interview?.timestamp ? new Date(interview.timestamp).toLocaleString('da-DK') : 'Ukendt dato'}
              </div>
            </div>
            <p className="text-sm text-gray-700 line-clamp-2">
              {interview?.transcript ? (interview.transcript.substring(0, 150) + '...') : 'Ingen transskription tilgængelig'}
            </p>
            <div className="flex justify-between items-center mt-3">
              <div className="text-sm text-gray-500">
                Varighed: {interview?.duration ? Math.floor(interview.duration / 60) : 0}:{interview?.duration ? (interview.duration % 60).toString().padStart(2, '0') : '00'}
              </div>
              <div className="text-sm font-medium text-blue-600">
                Samlet: {interview?.ratings?.samlet_karakter || 'N/A'}/10
              </div>
            </div>
          </div>
        )) : (
          <div className="text-center text-gray-500 py-8">
            {filter ? 'Ingen interviews matcher filteret' : 'Ingen interviews fundet'}
          </div>
        )}
      </div>
    </div>
  );
};

// Main App Component
const App = () => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState(null);
  const [overview, setOverview] = useState(null);
  const [themes, setThemes] = useState([]);
  const [ratings, setRatings] = useState({});
  const [interviews, setInterviews] = useState([]);
  const [selectedAssistant, setSelectedAssistant] = useState('Supermarket int. dansk');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);

  // Check authentication on app load
  useEffect(() => {
    const token = getStoredToken();
    const storedUser = getStoredUser();
    
    if (token && storedUser.email) {
      setIsAuthenticated(true);
      setUser(storedUser);
      setIsLoading(false);
    } else {
      setIsLoading(false);
    }
  }, []);

  const fetchAllData = useCallback(async (showLoading = true) => {
    if (showLoading) setIsLoading(true);
    setError(null);
    
    try {
      console.log('Fetching dashboard data...');
      
      const [overviewData, themesData, ratingsData, interviewsData] = await Promise.all([
        apiCall('overview'),
        apiCall('themes'),
        apiCall('ratings'),
        apiCall('interviews')
      ]);

      console.log('API responses:', { overviewData, themesData, ratingsData, interviewsData });

      setOverview(overviewData);
      setThemes(themesData.themes || []);
      setRatings(ratingsData.ratings || {});
      setInterviews(interviewsData.interviews || []);
      setLastUpdated(new Date().toLocaleTimeString('da-DK'));
      
      console.log('Dashboard data loaded successfully');
    } catch (error) {
      console.error('Error fetching dashboard data:', error);
      setError('Kunne ikke indlæse dashboard data. Tjek din internetforbindelse.');
    } finally {
      if (showLoading) setIsLoading(false);
    }
  }, []);

  // Fetch data when authenticated
  useEffect(() => {
    if (isAuthenticated) {
      fetchAllData();
      
      // Auto-refresh every 5 minutes
      const interval = setInterval(() => {
        fetchAllData(false); // Silent refresh
      }, 300000);
      
      return () => clearInterval(interval);
    }
  }, [isAuthenticated, fetchAllData]);

  const handleLogin = (loginData) => {
    setIsAuthenticated(true);
    setUser({
      email: loginData.email,
      accessLevel: loginData.access_level
    });
  };

  const handleLogout = () => {
    clearStoredAuth();
    setIsAuthenticated(false);
    setUser(null);
    setOverview(null);
    setThemes([]);
    setRatings({});
    setInterviews([]);
  };

  // Handle retry
  const handleRetry = () => {
    fetchAllData(true);
  };

  // Show loading on initial load
  if (isLoading && !isAuthenticated) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <LoadingSpinner message="Indlæser..." />
      </div>
    );
  }

  // Show landing page if not authenticated
  if (!isAuthenticated) {
    return <LandingPage onLogin={handleLogin} />;
  }

  // Show error state
  if (error && !overview) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="bg-white p-8 rounded-xl shadow-lg max-w-md">
          <ErrorMessage message={error} onRetry={handleRetry} />
        </div>
      </div>
    );
  }

  return (
    <ErrorBoundary>
      <div className="min-h-screen bg-gray-50">
        {/* Header */}
        <header className="bg-white shadow-sm border-b">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between items-center py-4">
              <div className="flex items-center space-x-4">
                <img 
                  src="/mindcalls-logo.png" 
                  alt="MindCalls" 
                  className="h-8 w-auto"
                />
                <span className="text-sm text-gray-500">
                  Kundeindsigter gennem AI-interviews
                </span>
                {lastUpdated && (
                  <span className="text-xs text-gray-400">
                    Sidst opdateret: {lastUpdated}
                  </span>
                )}
              </div>
              
              <div className="flex items-center space-x-4">
                <span className="text-sm text-gray-600">
                  {user?.email} ({user?.accessLevel})
                </span>
                <select 
                  value={selectedAssistant}
                  onChange={(e) => setSelectedAssistant(e.target.value)}
                  className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  disabled={isLoading}
                >
                  <option value="Supermarket int. dansk">Supermarket int. dansk</option>
                </select>
                <button 
                  onClick={() => fetchAllData(true)}
                  disabled={isLoading}
                  className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2"
                >
                  <span>{isLoading ? '⟳' : '🔄'}</span>
                  <span>{isLoading ? 'Opdaterer...' : 'Opdater'}</span>
                </button>
                <button 
                  onClick={handleLogout}
                  className="px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600"
                >
                  Log ud
                </button>
              </div>
            </div>
          </div>
        </header>

        {/* Main Content */}
        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          {error && (
            <div className="mb-6">
              <ErrorMessage message={error} onRetry={handleRetry} />
            </div>
          )}
          
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            {/* Row 1: Overview and Ratings */}
            <OverviewWidget overview={overview} isLoading={isLoading} />
            <RatingsWidget ratings={ratings} isLoading={isLoading} />
            
            {/* Row 2: Theme Collector (Full Width) */}
            <div className="lg:col-span-2">
              <ThemeCollectorWidget themes={themes} isLoading={isLoading} />
            </div>
            
            {/* Row 3: Enhanced Interview Reader (Full Width) */}
            <div className="lg:col-span-2">
              <EnhancedInterviewReaderWidget interviews={interviews} isLoading={isLoading} user={user} />
            </div>
          </div>
        </main>

        {/* Footer */}
        <footer className="bg-white border-t mt-12">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
            <div className="text-center text-sm text-gray-500">
              MindCalls v1.0 - Protected Access ✅
              {overview && (
                <span className="ml-4">
                  Aktive interviews: {overview.total_interviews} | 
                  Assistent: {overview.assistant_name}
                </span>
              )}
            </div>
          </div>
        </footer>
      </div>
    </ErrorBoundary>
  );
};

export default App;