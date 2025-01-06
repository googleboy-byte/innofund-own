# InnoFund - Decentralized Research Funding Platform

InnoFund is a modern web application that connects researchers with potential funders, enabling decentralized research funding through blockchain technology. The platform provides a transparent, efficient, and secure way to fund research projects using cryptocurrency.

## Features

### For Researchers
- Create and manage research project proposals
- Set funding goals and track progress
- Upload project documentation
- Build project teams
- Receive direct funding through cryptocurrency
- Track transaction history
- Manage project status (active/inactive)

### For Funders
- Browse active research projects
- View detailed project information
- Make direct cryptocurrency contributions
- Track contribution history
- Interact with project creators
- Vote on projects (upvote/downvote)

### General Features
- User authentication with OAuth
- Cryptocurrency wallet integration
- Real-time funding updates
- Responsive design for all devices
- Profile customization
- Social sharing capabilities
- Project search and filtering

## Technology Stack

- **Frontend**:
  - HTML5
  - CSS3 with modern features
  - JavaScript (ES6+)
  - Responsive design with Flexbox and Grid
  - Font Awesome icons
  - Inter font family

- **Backend**:
  - Python
  - Flask web framework
  - Firebase services:
    - Firestore (user data)
    - Realtime Database (project data)
    - Storage (file uploads)
    - Authentication

- **Blockchain Integration**:
  - Web3.js
  - MetaMask wallet support
  - Ethereum network

## Getting Started

### Prerequisites
- Python 3.8 or higher
- Node.js and npm
- Firebase account
- MetaMask wallet

### Installation

1. Clone the repository:
```bash
git clone https://github.com/googleboy-byte/innofund.git
cd innofund
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install Python dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
Create a `.env` file in the root directory with the following:
```
FLASK_APP=my_flask_app
FLASK_ENV=development

# Firebase Configuration
FIREBASE_API_KEY=your_firebase_api_key
FIREBASE_AUTH_DOMAIN=your_firebase_auth_domain
FIREBASE_PROJECT_ID=your_firebase_project_id
FIREBASE_STORAGE_BUCKET=your_firebase_storage_bucket
FIREBASE_MESSAGING_SENDER_ID=your_firebase_messaging_sender_id
FIREBASE_APP_ID=your_firebase_app_id
FIREBASE_MEASUREMENT_ID=your_firebase_measurement_id
FIREBASE_DATABASE_URL=your_firebase_database_url

# Firebase Admin Configuration
FIREBASE_ADMIN_PROJECT_ID=your_firebase_admin_project_id
FIREBASE_ADMIN_PRIVATE_KEY_ID=your_firebase_admin_private_key_id
FIREBASE_ADMIN_PRIVATE_KEY=your_firebase_admin_private_key
FIREBASE_ADMIN_CLIENT_EMAIL=your_firebase_admin_client_email
FIREBASE_ADMIN_CLIENT_ID=your_firebase_admin_client_id
FIREBASE_ADMIN_AUTH_URI=your_firebase_admin_auth_uri
FIREBASE_ADMIN_TOKEN_URI=your_firebase_admin_token_uri
FIREBASE_ADMIN_AUTH_PROVIDER_X509_CERT_URL=your_firebase_admin_auth_provider_cert_url
FIREBASE_ADMIN_CLIENT_X509_CERT_URL=your_firebase_admin_client_cert_url
```

5. Set up Firebase:
- Create a new Firebase project at [Firebase Console](https://console.firebase.google.com/)
- Enable the following services:
  - Authentication (with Google OAuth)
  - Firestore Database
  - Realtime Database
  - Storage
- Go to Project Settings > General to get your Firebase configuration values
- Go to Project Settings > Service Accounts to generate a new private key for Admin SDK
- Copy the configuration values to your `.env` file
- Update the Firebase Rules for each service according to your security requirements

6. Run the application:
```bash
flask run
```

The application will be available at `http://localhost:5000`

## Project Structure

```
innofund/
├── my_flask_app/
│   ├── app/
│   │   ├── static/
│   │   │   ├── css/
│   │   │   ├── js/
│   │   │   └── img/
│   │   ├── templates/
│   │   ├── __init__.py
│   │   ├── routes.py
│   │   ├── models.py
│   │   └── auth.py
│   └── config.py
├── requirements.txt
├── .env
└── README.md
```

## Security Features

- Secure authentication with Firebase
- Protected API endpoints
- Data validation and sanitization
- Secure file upload handling
- Rate limiting
- Cross-Site Scripting (XSS) protection
- Cross-Site Request Forgery (CSRF) protection

## Contributing

1. Fork the repository
2. Create a new branch (`git checkout -b feature/improvement`)
3. Make your changes
4. Commit your changes (`git commit -am 'Add new feature'`)
5. Push to the branch (`git push origin feature/improvement`)
6. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- [Flask](https://flask.palletsprojects.com/)
- [Firebase](https://firebase.google.com/)
- [Web3.js](https://web3js.readthedocs.io/)
- [Font Awesome](https://fontawesome.com/)
- [Inter Font](https://fonts.google.com/specimen/Inter)

## Contact

For any inquiries or support, please contact us at support@innofund.com 
