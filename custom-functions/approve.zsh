function restart-approve-service() {
	REGION=$2
	SERVICE=$1
	CLUSTER=approve-$3
	for taskArn in $(aws ecs list-tasks --region $REGION --cluster $CLUSTER --service $SERVICE --desired-status RUNNING --output text --query taskArns); do aws ecs stop-task --region $REGION --cluster $CLUSTER --task $taskArn --output text --query "task.taskArn"; done;
}
