"use strict";
document.querySelector('#login-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector('button');
  const error = document.querySelector('#login-error');
  error.hidden = true; button.disabled = true;
  try {
    const body = JSON.stringify({username: form.elements.username.value, password: form.elements.password.value});
    const response = await fetch('/api/login', {method: 'POST', headers: {'Content-Type': 'application/json'}, body});
    if (!response.ok) throw new Error('Sign in failed. Check your credentials or try again later.');
    location.assign('/');
  } catch (exc) {
    error.textContent = exc.message; error.hidden = false; button.disabled = false;
  }
});
