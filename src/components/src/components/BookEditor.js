import React, { useState } from 'react';

const BookEditor = ({ onGenerateBook }) => {
  const [prompt, setPrompt] = useState('');
  const [genre, setGenre] = useState('Adventure');
  const [tone, setTone] = useState('Romantic');

  const handleGenerateBook = () => {
    onGenerateBook({ prompt, genre, tone });
  };

  return (
    <div>
      <h2>Create Your Book</h2>
      <textarea
        placeholder="Enter your book idea..."
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
      />
      <div>
        <label>Genre:</label>
        <select value={genre} onChange={(e) => setGenre(e.target.value)}>
          <option value="Adventure">Adventure</option>
          <option value="Romance">Romance</option>
          <option value="Sci-Fi">Sci-Fi</option>
          <option value="Horror">Horror</option>
        </select>
      </div>
      <div>
        <label>Tone:</label>
        <select value={tone} onChange={(e) => setTone(e.target.value)}>
          <option value="Romantic">Romantic</option>
          <option value="Dark Romantic">Dark Romantic</option>
          <option value="NSFW">NSFW</option>
          <option value="Hardcore">Hardcore</option>
        </select>
      </div>
      <button onClick={handleGenerateBook}>Generate Book</button>
    </div>
  );
};

export default BookEditor;
