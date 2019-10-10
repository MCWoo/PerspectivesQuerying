# Overview
This is a simple AWS application to query the Perspectives.org website periodically and send a notification when new classes are added to the listing. Best of all, it fits within free tier :D

# Deployment
Too lazy to write a deployment script. To deploy the CloudFormation stack:

    aws cloudformation deploy --stack-name PerspectivesQuerying --template-file resources/stack.yml --capabilities CAPABILITY_IAM

To deploy the Lambda function code, first install the dependencies in the src directory:

    cd src/
    pip install boto3 -t .
    pip install requests -t .
    pip install beautifulsoup4 -t .

Then zip up the package folders with `index.py` and run:

    aws lambda update-function-code --function-name "<Name of deployed lambda>" --zip-file fileb://<file you just zipped>
