# Use Ubuntu 22.04 as the base image
FROM ubuntu:22.04

# Set environment variables to noninteractive (for apt-get)
ENV DEBIAN_FRONTEND=noninteractive

# Set proxy environment variables
ENV http_proxy=http://172.17.0.1:7890
ENV https_proxy=http://172.17.0.1:7890
ENV HTTP_PROXY=http://172.17.0.1:7890
ENV HTTPS_PROXY=http://172.17.0.1:7890
ENV no_proxy=localhost,127.0.0.1
ENV NO_PROXY=localhost,127.0.0.1

ENV OPENAI_API_KEY=sk-
ENV OPENAI_API_BASE=https://api.bianxie.ai/v1

# Configure apt proxy
RUN echo 'Acquire::http::Proxy "http://172.17.0.1:7890";' > /etc/apt/apt.conf.d/proxy.conf && \
    echo 'Acquire::https::Proxy "http://172.17.0.1:7890";' >> /etc/apt/apt.conf.d/proxy.conf

# Install all system dependencies in one layer
RUN apt-get update && apt-get install -y \
    curl \
    sudo \
    nano \
    software-properties-common \
    vim \
    git \
    wget \
    python3 \
    python3-pip \
    unzip \
    tar \
    apt-transport-https \
    ca-certificates \
    lsb-release \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

# Add OpenJDK repository and install OpenJDK versions
RUN add-apt-repository ppa:openjdk-r/ppa \
    && apt-get update \
    && apt-get install -y openjdk-8-jdk openjdk-11-jdk openjdk-17-jdk \
    && rm -rf /var/lib/apt/lists/*

# Set JAVA_HOME (defaults to JDK 17)
ENV JAVA_HOME=/usr/lib/jvm/java-1.17.0-openjdk-amd64

# Install Maven versions
ENV MAVEN_DIR=/opt/maven
ARG MAVEN_VERSIONS="3.2.1 3.5.0 3.9.8"
RUN mkdir -p $MAVEN_DIR && \
    for version in $MAVEN_VERSIONS; do \
    wget https://archive.apache.org/dist/maven/maven-3/${version}/binaries/apache-maven-${version}-bin.tar.gz -P /tmp && \
    tar -xzf /tmp/apache-maven-${version}-bin.tar.gz -C $MAVEN_DIR && \
    rm /tmp/apache-maven-${version}-bin.tar.gz; \
    done

# Set default Maven version
ENV MAVEN_HOME=$MAVEN_DIR/apache-maven-3.9.8
ENV PATH=$MAVEN_HOME/bin:$PATH

# Configure Maven proxy
RUN mkdir -p ~/.m2 && \
    echo '<?xml version="1.0" encoding="UTF-8"?>' > ~/.m2/settings.xml && \
    echo '<settings>' >> ~/.m2/settings.xml && \
    echo '  <proxies>' >> ~/.m2/settings.xml && \
    echo '    <proxy>' >> ~/.m2/settings.xml && \
    echo '      <id>http-proxy</id>' >> ~/.m2/settings.xml && \
    echo '      <active>true</active>' >> ~/.m2/settings.xml && \
    echo '      <protocol>http</protocol>' >> ~/.m2/settings.xml && \
    echo '      <host>172.17.0.1</host>' >> ~/.m2/settings.xml && \
    echo '      <port>7890</port>' >> ~/.m2/settings.xml && \
    echo '      <nonProxyHosts>localhost|127.0.0.1</nonProxyHosts>' >> ~/.m2/settings.xml && \
    echo '    </proxy>' >> ~/.m2/settings.xml && \
    echo '    <proxy>' >> ~/.m2/settings.xml && \
    echo '      <id>https-proxy</id>' >> ~/.m2/settings.xml && \
    echo '      <active>true</active>' >> ~/.m2/settings.xml && \
    echo '      <protocol>https</protocol>' >> ~/.m2/settings.xml && \
    echo '      <host>172.17.0.1</host>' >> ~/.m2/settings.xml && \
    echo '      <port>7890</port>' >> ~/.m2/settings.xml && \
    echo '      <nonProxyHosts>localhost|127.0.0.1</nonProxyHosts>' >> ~/.m2/settings.xml && \
    echo '    </proxy>' >> ~/.m2/settings.xml && \
    echo '  </proxies>' >> ~/.m2/settings.xml && \
    echo '</settings>' >> ~/.m2/settings.xml

# Install Gradle versions
ENV GRADLE_DIR=/opt/gradle
ARG GRADLE_VERSIONS="6.8.2 7.6.4 8.9"
RUN mkdir -p $GRADLE_DIR && \
    for version in $GRADLE_VERSIONS; do \
    wget -q https://services.gradle.org/distributions/gradle-${version}-bin.zip -O /tmp/gradle-${version}-bin.zip && \
    unzip -q /tmp/gradle-${version}-bin.zip -d $GRADLE_DIR && \
    rm /tmp/gradle-${version}-bin.zip; \
    done

# Set default Gradle version
ENV GRADLE_HOME=$GRADLE_DIR/gradle-8.9
ENV PATH=$GRADLE_HOME/bin:$PATH

# Configure Gradle proxy
RUN mkdir -p ~/.gradle && \
    echo 'systemProp.http.proxyHost=172.17.0.1' > ~/.gradle/gradle.properties && \
    echo 'systemProp.http.proxyPort=7890' >> ~/.gradle/gradle.properties && \
    echo 'systemProp.https.proxyHost=172.17.0.1' >> ~/.gradle/gradle.properties && \
    echo 'systemProp.https.proxyPort=7890' >> ~/.gradle/gradle.properties && \
    echo 'systemProp.http.nonProxyHosts=localhost|127.0.0.1' >> ~/.gradle/gradle.properties

# Verify installations
RUN java -version && mvn -version && gradle --version

# Install Miniconda
ENV CONDA_DIR=/opt/conda
ENV PATH=$CONDA_DIR/bin:$PATH

RUN ARCH=$(uname -m) && \
    if [ "$ARCH" = "x86_64" ]; then \
    CONDA_URL=https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh; \
    elif [ "$ARCH" = "aarch64" ]; then \
    CONDA_URL=https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-aarch64.sh; \
    else \
    echo "Unsupported architecture: $ARCH"; exit 1; \
    fi && \
    wget --quiet $CONDA_URL -O /tmp/miniconda.sh && \
    chmod +x /tmp/miniconda.sh && \
    /tmp/miniconda.sh -b -p $CONDA_DIR && \
    rm /tmp/miniconda.sh && \
    conda clean -afy

# Verify Conda installation
RUN conda --version

# Configure Conda proxy
RUN conda config --set proxy_servers.http http://172.17.0.1:7890 && \
    conda config --set proxy_servers.https http://172.17.0.1:7890

# Accept Conda TOS (Feature added 7/15/2025)
RUN conda tos accept

# Set working directory (will be mounted at runtime)
RUN mkdir /iris
WORKDIR /iris

# Copy only environment.yml to create conda environment
COPY environment.yml /tmp/environment.yml

# Create conda environment
RUN conda env remove -n iris || true && \
    conda env create -f /tmp/environment.yml && \
    conda clean -afy

# Download and extract CodeQL directly into /iris/
RUN curl -L -o codeql.zip https://github.com/github/codeql-cli-binaries/releases/download/v2.23.2/codeql.zip && \
    unzip -qo codeql.zip -d /iris/ && \
    rm -f codeql.zip

# Add CodeQL to PATH
ENV PATH="/iris/codeql:${PATH}"

# Set up conda environment activation
SHELL ["/bin/bash", "-c"]
RUN ENV_NAME=$(head -1 /tmp/environment.yml | cut -d' ' -f2) && \
    conda init bash && \
    echo ". /opt/conda/etc/profile.d/conda.sh" >> ~/.bashrc && \
    echo "conda activate $ENV_NAME" >> ~/.bashrc

# Default command (bash shell)
CMD ["/bin/bash"]
