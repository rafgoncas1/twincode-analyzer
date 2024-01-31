const { createApp } = Vue;
const socket = io();

const app = {
    delimiters: ['[[', ']]'],
    data() {
        return {
            password: '',
            errorMessage: null,
            successMessage: null,
            sessions: [],
            notification: null,
            favourites: false,
        }
    },
    computed: {
        filteredSessions() {
            if (this.favourites) {
                return this.sessions.filter(session => session.favourite);
            }
            return this.sessions;
        }
    },

    mounted() {
        if (window.location.pathname == '/') {
            this.fetchSessions();
        }
    },

    methods: {
        login() {
            fetch('/api/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({password: this.password})
            })
            .then(response => {
                if (response.status == 200) {
                    return response.json();
                }
                throw new Error('Login failed');
            })
            .then(data => {
                this.successMessage = data.message;
                setTimeout(function() {
                    window.location.href = '/';
                }, 2000);
            })
            .catch(error => {
                this.errorMessage = error.message;
            });
        },

        logout() {
            fetch('/api/logout', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            })
            .then(response => {
                if (response.status == 200) {
                    return response.json();
                }
                throw new Error('Logout failed');
            })
            .then(data => {
                this.successMessage = data.message;
                socket.disconnect();
                window.location.href = '/';
            })
            .catch(error => {
                this.errorMessage = error.message;
            });
        },

        closeNotification() {
            this.notification = null;
        },

        fetchSessions() {
            fetch('/api/sessions')
            .then(response => {
                if (response.status == 200) {
                    return response.json();
                }
                throw new Error('Fetch sessions failed');
            })
            .then(data => {
                this.sessions = data;
            })
            .catch(error => {
                this.errorMessage = error.message;
            });
        },

        addRemoveFavourite(session) {
            newStatus = !session.favourite;
            fetch('/api/favourites/' + session.name, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({favourite: newStatus})
            })
            .then(response => {
                if (response.status != 200) {
                    throw new Error("Failed to update favourite status for " + session.name);
                }
            })
            .catch((error) => {
                this.notification = {title: session.name, message: error.message, error: true};
            });
        },
    },
};

const mounted = createApp(app).mount('#app')

// Socket.io events

socket.on('favouriteUpdated', (data) => {
    mounted.notification = {title: data.name, message: data.favourite ? "Added to favourites" : "Removed from favourites"};
    // Update favourite status in the sessions list
    mounted.sessions.forEach(session => {
        if (session.name == data.name) {
            session.favourite = data.favourite;
        }
    });
});