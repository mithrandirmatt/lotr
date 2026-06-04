# LotR TCG Project — Completed Task Tracker

Only list the current active issue here. This should serve as a reminder of what we are currently working on.

## Behaviors

When shelving an issue to work on another, ensure the current issue is queued in this file.

Ensure when working on an issue, that the issue is listed here while it is being worked on.
Once complete, remove from this file and move it to the issues-completed.md file.


## Current Issue(s) Being Worked:

- **LOT-007** - Login Screen.
  - First time launch without login.
    - UI Page will be Sign In / Register page.
      - Sign in:
        - UI:
          - Email or Unique Name text input
            - While typing, validate format (basic email regex or non-empty unique name) and show error if invalid.
            - While empty show nothing.
            - While invalid format, show red error text "Please enter a valid email or unique name."
            - While valid, show green text "Looks good!" or something.
          - Password
            - Text input, masked.
            - Validate on submit (not while typing) for minimum length (e.g. 8 characters) and show error if too short.
          - Button to submit
        - Submit:
          - Backend:
            - Endpoint: POST /api/v1/auth/login
            - Request body: { email, password }
            - Response:
              - success:{ access_token, refresh_token, user: { id, email, is_admin, is_moderator } }
              - failure: { error }
          - UI:
            - On submit:
              - call the login endpoint
              - Hide submit button.
              - Show loading indicator.
                - Filler for now, later will have a proper loader animation.
                - Just show text "Logging in..." for now.
                  - Cycle the dots every 500ms: "Logging in.", "Logging in..", "Logging in...", "Logging in."
            - On success: store access_token, refresh_token, user info in localStorage; redirect to Dashboard
              - Go to the homepage/dashboard page.
            - On failure:
              - show error message
              - allow retry
              - Show the submit button again.
              - Hide the loading indicator.
  - Register page:
    - UI:
      - Email text input
        - While typing, validate format (basic email regex) and show error if invalid.
        - While empty show nothing.
        - While invalid format, show red error text "Please enter a valid email."
        - While valid, show green text "Looks good!" or something.
        - On typing:
          - Check if email is already registered (call backend endpoint) and show error if so.
          - Endpoint: GET /api/v1/auth/check-email?email={email}
          - Response: { exists: true/false }
          - debounce the API call by 500ms to avoid excessive calls while typing.
            - This means only make the API call if the user has stopped typing for 500ms, to avoid making a call on every keystroke.
          - If exists, show red error text "This email is already registered."
          - If not exists, show green text "Email is available!" or something.
      - Unique Name text input
        - While typing, validate format (non-empty, no spaces) and show error if invalid.
        - While empty show nothing.
        - While invalid format, show red error text "Please enter a valid unique name (no spaces)."
        - While valid, show green text "Looks good!" or something.
        - On typing:
          - Check if unique name is already taken (call backend endpoint) and show error if so.
          - Endpoint: GET /api/v1/auth/check-unique-name?unique_name={unique_name}
          - Response: { exists: true/false }
          - debounce the API call by 500ms to avoid excessive calls while typing.
            - This means only make the API call if the user has stopped typing for 500ms, to avoid making a call on every keystroke.
          - If exists, show red error text "This unique name is already taken."
          - If not exists, show green text "Unique name is available!" or something.
      - Password
        - Text input, masked.
        - Validate on submit (not while typing) for minimum length (e.g. 8 characters) and show error if too short.
      - Confirm Password
        - Text input, masked.
        - Validate on submit (not while typing) to ensure it matches the password field and show error if it doesn't.
      - Button to submit
    - On Submit:
      - Backend:
        - Endpoint: POST /api/v1/auth/register
        - Request body: { email, unique_name, password, confirm_password }
        - Response:
          - success: { message: "Registration successful. Please log in." }
          - failure: { error }
      - UI:
        - On submit:
          - call the register endpoint
          - Hide submit button.
          - Show loading indicator.
            - Just show text "Registering..." for now.
              - Cycle the dots every 500ms: "Registering.", "Registering..", "Registering..."
        - On success: show success message, redirect to login page after 2 seconds
          - Show message "Registration successful. Please log in."
          - After 2 seconds, redirect to login page.
        - On failure:
          - show error message
          - allow retry
          - Show the submit button again.
          - Hide the loading indicator.
      - On Registration:
        - Create a new user in the database with the provided email and password (hashed).
        - Ensure the email is unique; if not, return an error.
        - By default, new users should have `is_admin=False` and `is_moderator=False`.
        - Return a success message on successful registration.
        - Users will need a database association to track their collection and decks.
          -  Database:
            - TBD.





## Queued Issues:

- **LOT-008** - Add AI play.
  - This will allow users to play against an AI opponent locally.
  - The AI should follow the same rules user selects.
  - We should make the AI difficulty adjustable, so users can choose to play against an easier or harder opponent.
    - Decks should be built for each difficulty level, and the AI should use the appropriate deck based on the selected difficulty.
    - Need to classify cards in the database by difficulty level, so we can build appropriate decks for the AI.
  - The AI should be able to make legal moves and should be able to win or lose based on the game state.
  - AI should use the same game logic as the online play, so we can ensure consistency between local and online play.

## Queued Issues:



