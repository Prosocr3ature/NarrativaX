import React, { useState } from 'react';
import BookEditor from './components/BookEditor';
import CharacterGenerator from './components/CharacterGenerator';
import { generateBook } from './api/bookService';
import { generateCharacter } from './api/characterService';

const App = () => {
  const [book, setBook] = useState(null);
  const [characters, setCharacters] = useState([]);

  const handleGenerateBook = async ({ prompt, genre, tone }) => {
    const generatedBook = await generateBook(prompt, genre, tone);
    setBook(generatedBook);
  };

  const handleGenerateCharacter = async ({ name, role, appearance }) => {
    const character = await generateCharacter(name, role, appearance);
    setCharacters([...characters, character]);
  };

  return (
    <div>
      <h1>NarrativaX</h1>
      <BookEditor onGenerateBook={handleGenerateBook} />
      <CharacterGenerator onGenerateCharacter={handleGenerateCharacter} />
      
      <div>
        <h2>Generated Book</h2>
        {book && (
          <div>
            <h3>{book.title}</h3>
            <p>{book.outline}</p>
            <div>{book.chapters}</div>
          </div>
        )}
      </div>

      <div>
        <h2>Generated Characters</h2>
        {characters.map((char, index) => (
          <div key={index}>
            <h3>{char.name}</h3>
            <p>{char.role}</p>
            <p>{char.appearance}</p>
          </div>
        ))}
      </div>
    </div>
  );
};

export default App;
