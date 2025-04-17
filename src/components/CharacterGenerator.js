import React, { useState } from 'react';

const CharacterGenerator = ({ onGenerateCharacter }) => {
  const [name, setName] = useState('');
  const [role, setRole] = useState('');
  const [appearance, setAppearance] = useState('');

  const handleGenerateCharacter = () => {
    onGenerateCharacter({ name, role, appearance });
  };

  return (
    <div>
      <h3>Generate Character</h3>
      <input
        type="text"
        placeholder="Character Name"
        value={name}
        onChange={(e) => setName(e.target.value)}
      />
      <input
        type="text"
        placeholder="Character Role"
        value={role}
        onChange={(e) => setRole(e.target.value)}
      />
      <textarea
        placeholder="Character Appearance"
        value={appearance}
        onChange={(e) => setAppearance(e.target.value)}
      />
      <button onClick={handleGenerateCharacter}>Generate Character</button>
    </div>
  );
};

export default CharacterGenerator;
