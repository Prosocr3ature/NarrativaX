import axios from 'axios';

const API_URL = 'https://your-backend-url/api/';

export const generateBook = async (prompt, genre, tone) => {
  try {
    const response = await axios.post(`${API_URL}/generateBook`, { prompt, genre, tone });
    return response.data;
  } catch (error) {
    console.error('Error generating book:', error);
  }
};
