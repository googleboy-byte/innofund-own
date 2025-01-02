// Initialize Firebase Authentication
const githubProvider = new firebase.auth.GithubAuthProvider();

function signInWithGithub(nextUrl) {
    // Use provided nextUrl or fallback to URL parameter or dashboard
    nextUrl = nextUrl || new URLSearchParams(window.location.search).get('next') || '/dashboard';

    firebase.auth()
        .signInWithPopup(githubProvider)
        .then((result) => {
            const user = result.user;
            
            // First, send user data to our backend
            fetch('/auth/github/callback', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    token: result.credential.accessToken,
                    user: {
                        uid: user.uid,
                        email: user.email,
                        displayName: user.displayName,
                        photoURL: user.photoURL
                    }
                })
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    // Get the ID token
                    return user.getIdToken();
                } else {
                    throw new Error(data.error || 'Unknown error occurred');
                }
            })
            .then(idToken => {
                // Redirect to callback with ID token
                window.location.href = `/auth/github/callback?id_token=${idToken}&next=${encodeURIComponent(nextUrl)}`;
            })
            .catch(error => {
                console.error('Backend error:', error);
                alert('Failed to complete login: ' + error.message);
            });
        })
        .catch((error) => {
            console.error('GitHub login error:', error);
            alert('Failed to login with GitHub: ' + error.message);
        });
} 