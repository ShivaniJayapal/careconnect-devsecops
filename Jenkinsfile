// CareConnect DevSecOps pipeline
// GitHub -> Jenkins -> Tests -> Bandit -> Docker build -> Trivy -> Docker Hub push -> Kubernetes -> Verify
pipeline {
    agent any

    options {
        disableConcurrentBuilds()
        timeout(time: 40, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '10'))
    }

    triggers {
        githubPush()
    }

    parameters {
        // Phase 2 (security gate only): false. Phase 3 (Kubernetes): change the default to true and push.
        booleanParam(name: 'DEPLOY_TO_K8S', defaultValue: false, description: 'Deploy the scanned image to Minikube')
    }

    environment {
        IMAGE_REPO   = 'shivanij2004/careconnect'
        K8S_NAMESPACE = 'careconnect'
        DEPLOYMENT   = 'careconnect'
        DOCKERHUB_CREDS = 'dockerhub-creds'   // Jenkins credential ID (username + access token)
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
                script {
                    def shortSha = sh(returnStdout: true, script: 'git rev-parse --short=7 HEAD').trim()
                    env.IMAGE_TAG = "${env.BUILD_NUMBER}-${shortSha}"     // unique and immutable, never "latest"
                    env.IMAGE = "${env.IMAGE_REPO}:${env.IMAGE_TAG}"
                    echo "Image for this build: ${env.IMAGE}"
                }
                sh 'mkdir -p reports'
            }
        }

        stage('Install dependencies') {
            steps {
                sh '''
                    python3 -m venv .venv
                    . .venv/bin/activate
                    pip install --upgrade pip
                    pip install -r requirements-dev.txt
                '''
            }
        }

        stage('Automated tests') {
            steps {
                sh '''
                    . .venv/bin/activate
                    pytest --junitxml=reports/pytest.xml
                '''
            }
            post {
                always { junit allowEmptyResults: true, testResults: 'reports/pytest.xml' }
            }
        }

        stage('Bandit security scan') {
            // Gate: fail on findings with severity MEDIUM or higher AND confidence MEDIUM or higher.
            steps {
                sh '''
                    . .venv/bin/activate
                    set +e
                    bandit -c bandit.yaml -r . -ll -ii -f txt -o reports/bandit.txt
                    RC=$?
                    bandit -c bandit.yaml -r . -ll -ii -f json -o reports/bandit.json > /dev/null 2>&1
                    cat reports/bandit.txt
                    if [ $RC -ne 0 ]; then
                        echo "SECURITY GATE FAILED: Bandit reported issues (or failed to run). Exit code $RC."
                        exit 1
                    fi
                    echo "Bandit gate passed."
                '''
            }
        }

        stage('Docker build') {
            steps {
                sh 'docker build --pull -t "$IMAGE" .'
            }
        }

        stage('Trivy image scan') {
            steps {
                sh '''
                    set +e
                    # 1) Full report for evidence (all severities, fixed or not). Never fails the build.
                    trivy image --no-progress --format table --output reports/trivy-full.txt "$IMAGE"
                    FULL_RC=$?

                    # 2) The gate: HIGH and CRITICAL vulnerabilities that already have a fix available.
                    #    Exit code 10 means "vulnerabilities found"; any other non-zero code means the scanner itself failed.
                    trivy image --no-progress --severity HIGH,CRITICAL --ignore-unfixed \
                        --exit-code 10 --format table --output reports/trivy-gate.txt "$IMAGE"
                    RC=$?
                    cat reports/trivy-gate.txt

                    if [ $RC -eq 10 ]; then
                        echo "SECURITY GATE FAILED: fixable HIGH/CRITICAL vulnerabilities found in $IMAGE."
                        exit 1
                    elif [ $RC -ne 0 ] || [ $FULL_RC -ne 0 ]; then
                        echo "SECURITY GATE FAILED: Trivy could not complete the scan (exit $RC / $FULL_RC). Not treating this as a pass."
                        exit 1
                    fi
                    echo "Trivy gate passed."
                '''
            }
        }

        stage('Push image to Docker Hub') {
            // Only reached when tests, Bandit and Trivy all passed.
            steps {
                withCredentials([usernamePassword(credentialsId: env.DOCKERHUB_CREDS,
                                                  usernameVariable: 'DH_USER', passwordVariable: 'DH_TOKEN')]) {
                    sh '''
                        echo "$DH_TOKEN" | docker login -u "$DH_USER" --password-stdin
                        docker push "$IMAGE"
                        docker logout
                    '''
                }
            }
        }

        stage('Kubernetes deployment') {
            when { expression { return params.DEPLOY_TO_K8S } }
            steps {
                sh '''
                    kubectl apply -f k8s/namespace.yaml
                    # Create the app secret inside the cluster once; the value never touches GitHub or the image.
                    kubectl -n "$K8S_NAMESPACE" get secret careconnect-secret >/dev/null 2>&1 || \
                      kubectl -n "$K8S_NAMESPACE" create secret generic careconnect-secret \
                        --from-literal=SECRET_KEY="$(openssl rand -hex 32)"
                    kubectl apply -f k8s/service.yaml
                    sed "s|IMAGE_PLACEHOLDER|$IMAGE|" k8s/deployment.yaml | kubectl apply -f -
                '''
            }
        }

        stage('Deployment verification') {
            when { expression { return params.DEPLOY_TO_K8S } }
            steps {
                sh '''
                    if ! kubectl -n "$K8S_NAMESPACE" rollout status deployment/"$DEPLOYMENT" --timeout=180s; then
                        echo "Rollout failed. Rolling back to the previous revision."
                        kubectl -n "$K8S_NAMESPACE" rollout undo deployment/"$DEPLOYMENT" || true
                        exit 1
                    fi
                    kubectl -n "$K8S_NAMESPACE" get pods -o wide
                    echo "Running image:"
                    kubectl -n "$K8S_NAMESPACE" get deployment "$DEPLOYMENT" -o jsonpath='{.spec.template.spec.containers[0].image}{"\\n"}'
                    # Call /health from inside the pod (works without exposing any port).
                    kubectl -n "$K8S_NAMESPACE" exec deploy/"$DEPLOYMENT" -- \
                      python -c "import urllib.request as u; r=u.urlopen('http://127.0.0.1:8000/health', timeout=5); print(r.status, r.read().decode())"
                '''
            }
        }
    }

    post {
        always {
            archiveArtifacts artifacts: 'reports/**', allowEmptyArchive: true
            // Remove only this build's image from the build host (other images are untouched).
            sh 'docker rmi "$IMAGE" || true'
        }
        success { echo "Pipeline succeeded: ${env.IMAGE}" }
        failure { echo 'Pipeline FAILED: nothing was deployed after the failing stage.' }
    }
}
