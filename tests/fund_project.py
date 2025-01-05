import sys
import random
import requests

def login(session):
    """
    Log in to the application using email/password
    """
    login_url = 'http://localhost:5000/login'
    login_data = {
        'email': 'your_test_email@example.com',
        'password': 'your_test_password'
    }
    
    print("\nLogging in...")
    response = session.post(login_url, data=login_data)
    return response.ok

def fund_project(project_id, amount=None):
    """
    Fund a project with a specified amount.
    If amount is not specified, it will generate a random amount between 0.1 and 1.0 ETH
    """
    # If amount not specified, generate random amount between 0.1 and 1.0 ETH
    if amount is None:
        amount = round(random.uniform(0.1, 1.0), 2)
    
    # Create a session to maintain cookies
    session = requests.Session()
    
    try:
        # First, log in
        if not login(session):
            print("Failed to log in")
            return False
            
        # Make the POST request to update project funds
        print(f"\nMaking request to fund project {project_id} with {amount} ETH...")
        
        url = f'http://localhost:5000/update-project-funds/{project_id}'
        headers = {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        }
        data = {'amount': amount}
        
        print(f"URL: {url}")
        print(f"Headers: {headers}")
        print(f"Data: {data}\n")
        
        response = session.post(url, headers=headers, json=data)
        
        print(f"Response Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print(f"Response Content: {response.text}\n")
        
        if response.status_code == 200:
            try:
                result = response.json()
                if result.get('success'):
                    print(f"Successfully funded project {project_id}")
                    print(f"Amount: {amount} ETH")
                    return True
                else:
                    print(f"Error: {result.get('error', 'Unknown error')}")
                    return False
            except ValueError as e:
                print(f"Error parsing JSON response: {str(e)}")
                print(f"Raw response: {response.text}")
                return False
        else:
            print(f"Error: HTTP {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"Network error: {str(e)}")
        return False
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python fund_project.py <project_id> [amount]")
        sys.exit(1)
        
    project_id = sys.argv[1]
    amount = float(sys.argv[2]) if len(sys.argv) > 2 else None
    
    fund_project(project_id, amount) 