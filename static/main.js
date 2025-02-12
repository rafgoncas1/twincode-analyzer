const { createApp } = Vue;
const socket = io();

const app = {
    delimiters: ['[[', ']]'],
    data() {
        return {
            password: '',
            errorMessage: null,
            successMessage: null,
            analyses: [],
            sessions: [],
            isLoading: true,
            notification: null,
            favourites: false,
            statusFilter: 'all',
            searchTerm: '',
            showModal: false,
            modalSession: null,
            form1: null,
            form2: null,
            showScrollTop: false,
            rooms: null,
            reviewers: null,
            selectedReviewers: null,
            mainReviewer: "",
            loadingReviewers: true,
            collectingData: false,
            form1Error: null,
            form2Error: null,
            selectedSessions: [],
            customName: '',
            nextPage: false,
        }
    },

    computed: {
        filteredAnalyses() {
            res = this.analyses;
            if (this.favourites) {
                res = res.filter(analysis => analysis.favourite);
            }
            if (this.statusFilter != 'all') {
                res = res.filter(analysis => analysis.status == this.statusFilter);
            }
            if (this.searchTerm != '') {
                let lowerCaseSearchTerm = this.searchTerm.toLowerCase();
                res = res.filter(analysis => analysis.name.toLowerCase().includes(lowerCaseSearchTerm));
            }
            return res;
        },
        filteredSessions() {
            res = this.sessions;
            if (this.searchTerm != '') {
                let lowerCaseSearchTerm = this.searchTerm.toLowerCase();
                res = res.filter(session => session.toLowerCase().includes(lowerCaseSearchTerm));
            }
            return res;
        },
        unreviewedRooms() {
            if (!this.rooms) {
                return [];
            }
            res = this.rooms.filter(room => {
                for (const block of room.blocks) {
                    unreviewedBlock = true;
                    for (const reviewer of block.reviewers) {
                        if (this.selectedReviewers.includes(reviewer.reviewer) && reviewer.percentage == 100) {
                            unreviewedBlock = false;
                            break;
                        }
                    }
                }
                return unreviewedBlock;
            });
            return res.map(room => room.roomId);
        },
        customUnreviewedRooms() {
            if (!this.rooms) {
                return {};
            }
            res = {};
            for (const [key, value] of Object.entries(this.rooms)) {
                res[key] = value.filter(room => {
                    for (const block of room.blocks) {
                        unreviewedBlock = true;
                        for (const reviewer of block.reviewers) {
                            if (this.selectedReviewers[key].includes(reviewer.reviewer) && reviewer.percentage == 100) {
                                unreviewedBlock = false;
                                break;
                            }
                        }
                    }
                    return unreviewedBlock;
                })
                    .map(room => room.roomId);
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
        if (window.location.pathname == '/' || window.location.pathname == '/custom') {
            this.fetchAnalyses();
        }
        window.addEventListener('scroll', this.checkScroll);
    },

    methods: {

        checkScroll() {
            this.showScrollTop = window.scrollY > 500;
        },

        scrollTop() {
            window.scrollTo({ top: 0, behavior: 'smooth' });
        },

        login() {
            fetch('/api/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ password: this.password })
            })
                .then(response => {
                    if (response.status == 200) {
                        return response.json();
                    }
                    throw new Error('Login failed');
                })
                .then(data => {
                    this.successMessage = data.message;
                    setTimeout(function () {
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

        fetchAnalyses() {
            fetch('/api/analyses')
                .then(response => {
                    if (response.status == 200) {
                        return response.json();
                    }
                    throw new Error('Fetch analyses failed');
                })
                .then(data => {
                    this.analyses = data;
                    if (window.location.pathname == '/custom') {
                        this.sessions = data.filter(analysis => !analysis.custom).map(analysis => { return analysis.name });
                    }
                    this.isLoading = false;
                })
                .catch(error => {
                    this.notification = { title: "Error", message: error.message, error: true };
                    this.isLoading = false;
                });
        },

        addRemoveFavourite(analysis) {
            newStatus = !analysis.favourite;
            fetch('/api/favourites/' + analysis.name, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ favourite: newStatus })
            })
                .then(response => {
                    if (response.status != 200) {
                        throw new Error("Failed to update favourite status for " + analysis.name);
                    }
                })
                .catch((error) => {
                    this.notification = { title: analysis.name, message: error.message, error: true };
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

        fetchReviewers(sessionName) {
            this.loadingReviewers = true;
            fetch('https://tagachat.vercel.app/api/analytics/' + sessionName + '/reviewers')
                .then(response => {
                    if (response.status == 200) {
                        return response.json();
                    } else {
                        throw new Error('Failed to fetch reviewers: ' + response.status + ' ' + response.statusText);
                    }
                })
                .then(data => {
                    this.rooms = data;
                    this.reviewers = new Set();
                    for (const room of this.rooms) {
                        for (const block of room.blocks) {
                            for (const reviewer of block.reviewers) {
                                this.reviewers.add(reviewer.reviewer);
                            }
                        }
                    }
                    console.log(this.reviewers);
                    this.selectedReviewers = Array.from(this.reviewers);
                    this.loadingReviewers = false;
                })
                .catch(error => {
                    this.loadingReviewers = false;
                });
        },

        fetchCustomReviewers() {
            this.loadingReviewers = true;
            this.rooms = {};
            this.reviewers = {};
            this.selectedReviewers = {};
            this.mainReviewer = {};
            let promises = [];

            for (const session of this.selectedSessions) {
                let promise = fetch('https://tagachat.vercel.app/api/analytics/' + session + '/reviewers')
                    .then(response => {
                        if (response.status == 200) {
                            return response.json();
                        } else {
                            throw new Error('Failed to fetch reviewers: ' + response.status + ' ' + response.statusText);
                        }
                    })
                    .then(data => {

                        this.rooms[session] = data;

                        const reviewersSet = new Set();
                        for (const room of this.rooms[session]) {
                            for (const block of room.blocks) {
                                for (const reviewer of block.reviewers) {
                                    reviewersSet.add(reviewer.reviewer);
                                }
                            }
                        }

                        this.reviewers[session] = reviewersSet;

                        this.selectedReviewers[session] = Array.from(this.reviewers[session]);

                        this.mainReviewer[session] = "";

                    })
                    .catch(error => {
                        this.rooms[session] = [];
                        this.reviewers[session] = new Set();
                        this.selectedReviewers[session] = [];
                        this.mainReviewer[session] = "";
                    });
                promises.push(promise);
            }

            Promise.all(promises).then(() => {
                this.loadingReviewers = false;
            });
        },

        removeFilters() {
            this.favourites = false;
            this.statusFilter = 'all';
            this.searchTerm = '';
        },

        viewAnalysis(analysis) {
            window.location.href = '/analysis/' + analysis.name;
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
            this.form1Error = null;
            this.form2Error = null;
            this.rooms = null;
            this.reviewers = null;
            this.selectedReviewers = null;
            this.mainReviewer = "";
        },

        handleFileUpload(event, formName) {

            if (formName != 'form1' && formName != 'form2') {
                return;
            }

            const file = event.target.files[0];

            Papa.parse(file, {
                header: true,
                complete: (results) => {
                    if (this.validateCSV(results, formName)) {
                        this[formName] = file;
                    } else {
                        event.target.value = null;
                    }
                },
                error: (error) => {
                    event.target.value = null;
                    this[formName + "Error"] = "Invalid file format: Unable to read csv"
                }
            });
        },

        validateCSV(data, formName) {
            if (formName == 'form1') {
                if (data.meta.fields.length != 11) {
                    this[formName + "Error"] = "Invalid file format: Incorrect number of columns, expected 11";
                    return false;
                } else {
                    var invalidColumns = []
                    var expectedToContain = ['', 'enter your', ...Array(4).fill('regarding'), ...Array(4).fill('during'), 'describe'];
                    for (let i = 1; i < 11; i++) {
                        if (!data.meta.fields[i].toLowerCase().includes(expectedToContain[i])) {
                            invalidColumns.push(i + 1);
                        }
                    }
                    if (invalidColumns.length > 0) {
                        this[formName + "Error"] = "Invalid file format: Incorrect column headers at columns " + invalidColumns.join(", ");
                        return false;
                    }
                }
            } else if (formName == 'form2') {
                if (data.meta.fields.length != 19) {
                    this[formName + "Error"] = "Invalid file format: Incorrect number of columns, expected 19";
                    return false;
                } else {
                    var invalidColumns = []
                    var expectedToContain = ['', 'enter your', ...Array(4).fill('regarding'), ...Array(4).fill('during'), 'describe', ...Array(5).fill('comparing'), ...Array(3).fill('remember')];
                    for (let i = 1; i < 19; i++) {
                        if (!data.meta.fields[i].toLowerCase().includes(expectedToContain[i])) {
                            invalidColumns.push(i + 1);
                        }
                    }
                    if (invalidColumns.length > 0) {
                        this[formName + "Error"] = "Invalid file format: Incorrect column headers at columns " + invalidColumns.join(", ");
                        return false;
                    }
                }
            }
            this[formName + "Error"] = null;
            return true;
        },



        startSessionAnalysis(session) {

            if (!this.form1 || !this.form2) {
                this.notification = { title: session.name, message: "Please select both files", error: true };
                return;
            }

            this.showModal = false;
            this.collectingData = true;

            const formData = new FormData();
            formData.append('form1', this.form1);
            formData.append('form2', this.form2);
            formData.append('reviewers', JSON.stringify(this.selectedReviewers));
            if (this.mainReviewer && this.mainReviewer.trim() !== '') {
                formData.append('mainReviewer', this.mainReviewer);
            }
            fetch('/api/analysis/' + session.name, {
                method: 'POST',
                body: formData,
            })
                .then(response => {
                    this.collectingData = false;
                    this.form1 = null;
                    this.form2 = null;
                    if (response.status != 202) {
                        this.showModal = true;
                        return response.json().then(data => {
                            throw new Error(data.message);
                        });
                    }
                    this.modalSession = null;
                })
                .catch((error) => {
                    this.notification = { title: session.name, message: error.message, error: true };
                });
        },

        startCustomAnalysis() {

            if (!this.form1 || !this.form2) {
                this.notification = { title: "Custom Analysis", message: "Please select both files", error: true };
                return;
            }

            this.collectingData = true;

            const formData = new FormData();
            formData.append('form1', this.form1);
            formData.append('form2', this.form2);
            formData.append('reviewers', JSON.stringify(this.selectedReviewers));
            formData.append('name', this.customName);
            formData.append('mainReviewer', JSON.stringify(this.mainReviewer));

            fetch('/api/analysis/custom', {
                method: 'POST',
                body: formData,
            })
                .then(response => {

                    if (response.status != 202) {
                        this.collectingData = false;
                        this.form1 = null;
                        this.form2 = null;
                        this.showModal = true;
                        return response.json().then(data => {
                            throw new Error(data.message);
                        });
                    }
                    this.collectingData = false;
                    window.location.href = '/';
                })
                .catch((error) => {
                    this.notification = { title: "Custom Analysis", message: error.message, error: true };
                });
        },

        printPage() {
            window.print();
        }
    },


    beforeDestroy() {
        window.removeEventListener('scroll', this.checkScroll);
    }
};

const mounted = createApp(app).mount('#app')

// Socket.io events

socket.on('favouriteUpdated', (data) => {
    mounted.notification = { title: data.name, message: data.favourite ? "Added to favourites" : "Removed from favourites" };
    // Update favourite status in the sessions list
    mounted.analyses.forEach(analysis => {
        if (analysis.name == data.name) {
            analysis.favourite = data.favourite;
        }
    });
});

socket.on('analysisStarted', (data) => {
    const { showModal, modalSession, closeModal } = mounted;
    if (showModal && modalSession.name == data.name) {
        closeModal();
    }

    mounted.notification = { title: data.name, message: "Analysis started" };
    // Update status in the sessions list
    mounted.analyses.forEach(analysis => {
        if (analysis.name == data.name) {
            analysis.status = "running";
            analysis.percentage = 1;
        }
    });
});

socket.on('analysisError', (data) => {
    mounted.notification = { title: data.name, message: data.message, error: true };
    // Update status in the sessions list
    mounted.analyses.forEach(analysis => {
        if (analysis.name == data.name) {
            analysis.status = "pending";
            analysis.percentage = 0;
        }
    });
});

socket.on('percentageUpdate', (data) => {
    // Update percentage in the sessions list
    mounted.analyses.forEach(analysis => {
        if (analysis.name == data.name) {
            analysis.percentage = data.percentage;
        }
    });
});

socket.on('analysisCompleted', (data) => {
    mounted.notification = { title: data.name, message: "Analysis completed" };
    // Update status in the sessions list
    mounted.analyses.forEach(analysis => {
        if (analysis.name == data.name) {
            analysis.status = "completed";
            analysis.percentage = 100;
        }
    });
});