import express from 'express';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const router = express.Router();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const DB_FILE = path.join(__dirname, '../users.json');

function readUsers() {
  try {
    if (!fs.existsSync(DB_FILE)) {
      return [];
    }
    const data = fs.readFileSync(DB_FILE, 'utf8');
    return JSON.parse(data || '[]');
  } catch (error) {
    console.error('Error reading users database:', error);
    return [];
  }
}

function writeUsers(users) {
  try {
    fs.writeFileSync(DB_FILE, JSON.stringify(users, null, 2), 'utf8');
  } catch (error) {
    console.error('Error writing users database:', error);
  }
}

router.post('/signup', async (req, res) => {
  try {
    const { firstName, lastName, address, postalCode, email, password } = req.body;
    if (!email || !password) {
      return res.status(400).json({ error: 'Email and password are required' });
    }

    const users = readUsers();
    const exists = users.find(u => u.email.toLowerCase() === email.toLowerCase());
    if (exists) {
      return res.status(400).json({ error: 'Email already registered' });
    }

    const newUser = {
      id: users.length > 0 ? Math.max(...users.map(u => u.id)) + 1 : 1,
      firstName: firstName || '',
      lastName: lastName || '',
      address: address || '',
      postalCode: postalCode || '',
      email: email.toLowerCase(),
      password: password
    };

    users.push(newUser);
    writeUsers(users);

    res.json({ message: 'Sign up successful.' });
  } catch (error) {
    console.error('Error signing up:', error);
    res.status(500).json({ error: error.message });
  }
});

router.post('/signin', async (req, res) => {
  try {
    const { email, password } = req.body;
    if (!email || !password) {
      return res.status(400).json({ error: 'Email and password are required' });
    }

    const users = readUsers();
    const user = users.find(u => u.email.toLowerCase() === email.toLowerCase() && u.password === password);
    if (!user) {
      return res.status(400).json({ error: 'Invalid email or password' });
    }

    const token = `mock-jwt-token-for-user-${user.id}`;
    
    const userResponse = {
      id: user.id,
      firstName: user.firstName,
      lastName: user.lastName,
      address: user.address,
      postalCode: user.postalCode,
      email: user.email
    };

    res.json({
      message: 'Sign in successful.',
      token,
      user: userResponse
    });
  } catch (error) {
    console.error('Error signing in:', error);
    res.status(500).json({ error: error.message });
  }
});

router.put('/profile', async (req, res) => {
  try {
    const token = req.headers.authorization;
    if (!token || !token.startsWith('mock-jwt-token-for-user-')) {
      return res.status(401).json({ error: 'No token provided or invalid token' });
    }

    const userId = parseInt(token.replace('mock-jwt-token-for-user-', ''), 10);
    const users = readUsers();
    const userIdx = users.findIndex(u => u.id === userId);
    if (userIdx === -1) {
      return res.status(404).json({ error: 'User not found' });
    }

    const { firstName, lastName, address, postalCode, email, password } = req.body;
    
    if (firstName !== undefined) users[userIdx].firstName = firstName;
    if (lastName !== undefined) users[userIdx].lastName = lastName;
    if (address !== undefined) users[userIdx].address = address;
    if (postalCode !== undefined) users[userIdx].postalCode = postalCode;
    if (email !== undefined) users[userIdx].email = email.toLowerCase();
    if (password !== undefined) users[userIdx].password = password;

    writeUsers(users);

    const updatedUser = {
      id: users[userIdx].id,
      firstName: users[userIdx].firstName,
      lastName: users[userIdx].lastName,
      address: users[userIdx].address,
      postalCode: users[userIdx].postalCode,
      email: users[userIdx].email
    };

    res.json({
      message: 'Profile updated successfully.',
      user: updatedUser
    });
  } catch (error) {
    console.error('Error updating profile:', error);
    res.status(500).json({ error: error.message });
  }
});

export default router;