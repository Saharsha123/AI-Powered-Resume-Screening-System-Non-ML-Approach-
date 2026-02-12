document.addEventListener('DOMContentLoaded', () => {
    // Smooth Scroll Behavior
    document.documentElement.style.scrollBehavior = 'smooth';

    // Floating Label Logic for Inputs and Textareas (exclude file inputs)
    const inputs = document.querySelectorAll('.form-input:not([type="file"]), .form-textarea');
    inputs.forEach(input => {
        const updateLabel = () => {
            const formGroup = input.closest('.form-group');
            if (input.value.trim() !== '') {
                formGroup.classList.add('filled');
            } else {
                formGroup.classList.remove('filled');
            }
        };

        // Check on input and change events
        input.addEventListener('input', updateLabel);
        input.addEventListener('change', updateLabel);

        // Check on page load in case the input has a value (e.g., from browser autofill)
        updateLabel();
    });

    // Form Validation for Login
    const loginForm = document.getElementById('login-form');
    if (loginForm) {
        loginForm.addEventListener('submit', (e) => {
            const username = document.getElementById('username').value.trim();
            const password = document.getElementById('password').value.trim();

            if (!username || !password) {
                e.preventDefault();
                alert('Please fill in all fields.');
            }
        });
    }

    // Form Validation for Register
    const registerForm = document.getElementById('register-form');
    if (registerForm) {
        registerForm.addEventListener('submit', (e) => {
            const username = document.getElementById('username').value.trim();
            const password = document.getElementById('password').value.trim();
            const confirmPassword = document.getElementById('confirm-password').value.trim();

            if (!username || !password || !confirmPassword) {
                e.preventDefault();
                alert('Please fill in all fields.');
            } else if (password !== confirmPassword) {
                e.preventDefault();
                alert('Passwords do not match.');
            }
        });
    }

    // Form Validation and Loading Spinner for Upload
    const uploadForm = document.getElementById('upload-form');
    const loadingSpinner = document.getElementById('loading-spinner');
    if (uploadForm) {
        uploadForm.addEventListener('submit', (e) => {
            const jobDesc = document.getElementById('job_desc').value.trim();
            const resumeFile = document.getElementById('resume').files[0];

            // Validate Job Description
            if (!jobDesc) {
                e.preventDefault();
                alert('Please enter a job description.');
                return;
            }

            // Validate File
            if (!resumeFile) {
                e.preventDefault();
                alert('Please upload a resume file.');
                return;
            }

            const allowedExtensions = ['pdf', 'doc', 'docx'];
            const maxFileSize = 5 * 1024 * 1024; // 5MB
            const fileExtension = resumeFile.name.split('.').pop().toLowerCase();
            if (!allowedExtensions.includes(fileExtension)) {
                e.preventDefault();
                alert('Invalid file type. Please upload a PDF, DOC, or DOCX file.');
                return;
            }

            if (resumeFile.size > maxFileSize) {
                e.preventDefault();
                alert('File size exceeds 5MB. Please upload a smaller file.');
                return;
            }

            // Show Loading Spinner
            if (loadingSpinner) {
                loadingSpinner.style.display = 'block';
            }
        });
    }

    // Table Sorting for Dashboard
    const resultsTable = document.getElementById('results-table');
    if (resultsTable) {
        const headers = resultsTable.querySelectorAll('th[data-sort]');
        let sortDirection = {};

        headers.forEach(header => {
            header.addEventListener('click', () => {
                const key = header.getAttribute('data-sort');
                const tbody = resultsTable.querySelector('tbody');
                const rows = Array.from(tbody.querySelectorAll('tr'));

                // Toggle sort direction
                sortDirection[key] = !sortDirection[key] || sortDirection[key] === 'desc' ? 'asc' : 'desc';
                
                // Update aria-sort attribute
                headers.forEach(h => h.setAttribute('aria-sort', 'none'));
                header.setAttribute('aria-sort', sortDirection[key]);

                // Sort rows
                rows.sort((a, b) => {
                    const aValue = a.children[Array.from(headers).indexOf(header)].textContent.trim();
                    const bValue = b.children[Array.from(headers).indexOf(header)].textContent.trim();

                    if (key === 'date') {
                        // Sort dates
                        const aDate = new Date(aValue);
                        const bDate = new Date(bValue);
                        return sortDirection[key] === 'asc' ? aDate - bDate : bDate - aDate;
                    } else if (key === 'result' || key === 'matches') {
                        // Sort numbers (e.g., Result or Matches)
                        const aNum = parseFloat(aValue);
                        const bNum = parseFloat(bValue);
                        return sortDirection[key] === 'asc' ? aNum - bNum : bNum - aNum;
                    } else {
                        // Sort strings
                        return sortDirection[key] === 'asc'
                            ? aValue.localeCompare(bValue)
                            : bValue.localeCompare(aValue);
                    }
                });

                // Re-append sorted rows
                tbody.innerHTML = '';
                rows.forEach(row => tbody.appendChild(row));
            });
        });
    }
});

document.addEventListener('DOMContentLoaded', function () {
    const form = document.getElementById('upload-form');
    const resultSection = document.getElementById('result-section');
    const loadingSpinner = document.getElementById('loading-spinner');
    const jobDescInput = document.getElementById('job_desc');
    const jobDescError = document.getElementById('job-desc-error');

    form.addEventListener('submit', function (event) {
        event.preventDefault(); // Prevent default form submission

        // Validate job description
        const jobDescValue = jobDescInput.value.trim();
        if (!jobDescValue) {
            jobDescError.style.display = 'block';
            return; // Stop submission if validation fails
        }
        jobDescError.style.display = 'none';

        // Show loading spinner
        loadingSpinner.style.display = 'block';
        resultSection.style.display = 'none';
        resultSection.innerHTML = ''; // Clear previous results

        // Create FormData object to send form data
        const formData = new FormData(form);

        // Log FormData for debugging (optional, can remove in production)
        for (let [key, value] of formData.entries()) {
            console.log(`${key}: ${value}`);
        }

        // Send AJAX request
        fetch('/upload', {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest' // Indicate AJAX request
            }
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            // Hide loading spinner
            loadingSpinner.style.display = 'none';

            // Check for error in response
            if (data.error) {
                resultSection.innerHTML = `<p style="color: red;">Error: ${data.error}</p>`;
                resultSection.style.display = 'block';
                return;
            }

            // Calculate ranking score
            const skillsLength = data.skills_length || data.skills.length;
            const rankingScore = skillsLength > 0 ? ((data.match_count / skillsLength) * 100).toFixed(2) : 0;

            // Display analysis results
            resultSection.innerHTML = `
                <h2 class="results-title">Analysis Result</h2>
                <p><strong>Overall Result:</strong> ${data.result}</p>
                <p><strong>Overall Score:</strong> ${data.overall_score}%</p>
                <h3>Skills Analysis</h3>
                <p><strong>Job Skills:</strong> ${data.skills.join(', ')}</p>
                <p><strong>Resume Skills:</strong> ${data.resume_skills.join(', ')}</p>
                <p><strong>Matched Skills:</strong> ${data.match_count} / ${skillsLength}</p>
                <p><strong>Skills Score:</strong> ${rankingScore}%</p>
                <h3>Education Analysis</h3>
                <p><strong>Education Match:</strong> ${data.education_result ? 'Pass' : 'Fail'}</p>
                <p><strong>Education Score:</strong> ${data.education_score}%</p>
                <h3>Experience Analysis</h3>
                <p><strong>Experience Match:</strong> ${data.experience_result ? 'Pass' : 'Fail'}</p>
                <p><strong>Experience Score:</strong> ${data.experience_score}%</p>
            `;
            resultSection.style.display = 'block';
        })
        .catch(error => {
            // Hide loading spinner
            loadingSpinner.style.display = 'none';

            console.error('Error:', error);
            resultSection.innerHTML = '<p style="color: red;">An error occurred while analyzing the resume. Please try again.</p>';
            resultSection.style.display = 'block';
        });
    });

    // Clear error message when user starts typing
    jobDescInput.addEventListener('input', function () {
        jobDescError.style.display = 'none';
    });
});