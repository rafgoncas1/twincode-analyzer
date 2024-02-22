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
            loaded: false,
            notification: null,
            favourites: false,
            statusFilter: 'all',
            searchTerm: '',
            showModal: false,
            modalSession: null,
            form1: null,
            form2: null
        }
    },

    computed: {
        filteredSessions() {
            res = this.sessions;
            if (this.favourites) {
                res = this.sessions.filter(session => session.favourite);
            }
            if (this.statusFilter != 'all') {
                res = res.filter(session => session.status == this.statusFilter);
            }
            if (this.searchTerm != '') {
                let lowerCaseSearchTerm = this.searchTerm.toLowerCase();
                res = res.filter(session => session.name.toLowerCase().includes(lowerCaseSearchTerm));
            }
            return res;
        }
    },

    watch: {
        showModal(val) {
            if (val) {
                document.body.style.overflow = 'hidden';
            } else {
                document.body.style.overflow = 'auto';
            }
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
                this.notification = {title: "Error", message: error.message, error: true};
            });
                this.loaded = true;
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

        nextStatusFilter() {
            if (this.statusFilter == 'all') {
                this.statusFilter = 'completed';
            } else if (this.statusFilter == 'completed') {
                this.statusFilter = 'running';
            } else if (this.statusFilter == 'running') {
                this.statusFilter = 'pending';
            } else {
                this.statusFilter = 'all';
            }
        },

        removeFilters() {
            this.favourites = false;
            this.statusFilter = 'all';
            this.searchTerm = '';
        },

        viewAnalysis(session) {
            window.location.href = '/analysis/' + session.name;
        },

        openModal(session) {
            this.modalSession = session;
            this.showModal = true;
        },

        closeModal() {
            this.showModal = false;
            this.modalSession = null;
            this.form1 = null;
            this.form2 = null;
        },

        handleFileUpload(event, formName) {
            this[formName] = event.target.files[0];
            console.log(this[formName]);
        },

        startAnalysis(session) {
            const formData = new FormData();
            formData.append('form1', this.form1);
            formData.append('form2', this.form2);

            fetch('/api/analysis/' + session.name, {
                method: 'POST',
                body: formData,
            })
            .then(response => {
                if (response.status != 202) {
                    throw new Error("Failed to start analysis for " + session.name);
                }
            })
            .catch((error) => {
                this.notification = {title: session.name, message: error.message, error: true};
            });
        }
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

socket.on('analysisStarted', (data) => {
    const { showModal, modalSession, closeModal } = mounted;
    if (showModal && modalSession.name == data.name) {
        closeModal();
    }

    notification = {title: data.name, message: "Analysis started"};
    // Update status in the sessions list
    sessions.forEach(session => {
        if (session.name == data.name) {
            session.status = "running";
            session.percentage = 1;
        }
    });
});

socket.on('analysisError', (data) => {
    mounted.notification = {title: data.name, message: data.message, error: true};
    // Update status in the sessions list
    mounted.sessions.forEach(session => {
        if (session.name == data.name) {
            session.status = "pending";
            session.percentage = 0;
        }
    });
});

socket.on('percentageUpdate', (data) => {
    // Update percentage in the sessions list
    mounted.sessions.forEach(session => {
        if (session.name == data.name) {
            session.percentage = data.percentage;
        }
    });
});