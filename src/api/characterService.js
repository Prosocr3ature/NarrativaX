import axios from 'axios';

const API_URL = 'https://your-backend-url/api/';

export const generateCharacter = async (outline, genre, tone) => {
  try {
    const response = await axios.post(`${API_URL}/generateCharacter`, { outline, genre, tone });
    return response.data;
  } catch (error) {
    console.error('Error generating character:', error);
  }
};
