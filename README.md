# serratus
*Ultra-high throughput processing of SRA data on AWS*
![Serratus Mountain in Squamish, BC. Canada](img/serratus_logo.png)

COVID-19 came out of seemingly nowhere. We will ultra-deep search all SRA sequence data to find coronaviruses and trace the lineage of SARS-CoV-2. 

#### Architecture
![serratus-overview](img/serratus_overview.png)

## Repository organization
### Folders

`docker/`: Container make files and tokens

`img/`: Architecture/workflow diagrams

`packer/`: Standardized node images (ami)

`scheduler/`: Code for `serratus` head-node and sraRunInfo management

`scripts/`: Defined units of work performed in `serratus`

`terraform/`: Cloud resources / pipeline management


### S3 Bucket
**s3://serratus-public/**

**$S3/resources**: Genome indices
- hgr1/ : human rDNA bowtie2 indexed

**$S3/example-data**: Toy data for testing
- bam/ : aligned bam files for breaking into blocks
- fq/  : sequencing reads of various length


## Useful links
- **S3 Bucket:** s3://serratus-public/ (public-readable)
- [Alpine Linux AMI](https://github.com/mcrute/alpine-ec2-ami)
- [AWS Batch workflow - Introduction](https://aws.amazon.com/blogs/compute/building-high-throughput-genomics-batch-workflows-on-aws-introduction-part-1-of-4/)
- [AWS Batch workflow - github](https://github.com/aws-samples/aws-batch-genomics)
- [FSx Shared file-system for HPC](https://aws.amazon.com/blogs/storage/using-amazon-fsx-for-lustre-for-genomics-workflows-on-aws/)
- [SRA in the Cloud -- Use SRA Toolkit](https://www.ncbi.nlm.nih.gov/sra/docs/sra-cloud/)
- [SRA Data Registry on S3](https://registry.opendata.aws/ncbi-sra/)
- [S3 transfer optimization](https://docs.aws.amazon.com/cli/latest/topic/s3-config.html)
- [Paper on analyzing EC2 costs (2011)](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0026624)
- [Pushing the limits of Amazon S3 Upload Performance](https://improve.dk/pushing-the-limits-of-amazon-s3-upload-performance/)
- [Clever SRA alignment pipeline](https://github.com/FredHutch/sra-pipeline
)
- [Interpretable detection of novel human viruses from genome sequencing data](https://www.biorxiv.org/content/10.1101/2020.01.29.925354v3.full.pdf)
- [Bigsi: Bloom filter indexing of SRA/ENA for organism search](https://github.com/phelimb/bigsi)
- [Virus detection from RNA-seq proof of concept paper](https://www.ncbi.nlm.nih.gov/pubmed/21603639)


# Getting up and running

## 1) Building AMIs with Packer

First, [download Packer](https://packer.io/downloads.html).  It comes as a single
binary which you can just unzip.  I extracted it to `~/.local/bin` so that it ended
up on my PATH.

Next, use it to build the AMI: `/path/to/packer build serratus/packer/docker-ami.json`

This will start up a t3.nano, build the AMI, and then terminate it.  Currently this
takes about 2 minutes, which should cost well under a penny.

## 2) Getting started with Terraform

### Variables

Before starting, you'll need to [setup a keypair on EC2](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-key-pairs.html#having-ec2-create-your-key-pair).  Make sure to use the us-east-1 region, as that's where the SRA data is stored.  Keep the name of the keypair, you'll need it later.

You'll also need to find out your public IP.  Try `curl ipecho.net/plain; echo`.

Open terraform/main/terraform.tfvars.  There are three environment variables in this file:

 * `dev_cidrs`: Your public IP, followed by "/32"
 * `key_name`: EC2 key pair name
 * `dockerhub_account`: Where the docker images are stored.  You can leave it as-is if you don't want to build the images.

### Init

The top-level module is in serratus/terraform/main.  Change directory to there,
run `tf init`, and then `tf apply` to create some infrastructure.

At the time of writing, this will create:

  * a t3.nano, for the scheduler, with an Elastic IP
  * an S3 bucket, to store intermediates
  * an ASG for serratus-dl, using c5.large with 50GB of gp2.
  * An ASG for serratus-align, using c5.large
  * An ASG for serratus-merge, using t3.small
  * Security groups and IAM roles to tie it all together.

All ASGs have a max size of 1.  This can all be reconfigured in terraform/main/main.tf.

At the end of `tf apply`, it will output the scheduler's DNS address.  Keep this
for later.

### Creating an SSH Tunnel to the scheduler

By default, the scheduler exposes port 8000.  This port is *not* exposed to the public
internet because it doesn't support any authentication or encryption yet.  You'll need
to create an SSH tunnel to allow your local web-browser and terminal to connect.  

    $ scheduler_dns=<copied this from terraform>
    $ ssh -L 8000:localhost:8000 ec2-user@$scheduler_dns

Leave this terminal open.  It will route requests from port 8000 on your local machine
to the application running on the scheduler.

To test this, open a web browser at [http://localhost:8000/jobs/](http://localhost:8000/jobs/).
You should some table headings with no actual data.  If so, the scheduler is ready to be loaded.
The scheduler takes a few minutes to boot up.  If you're seeing strange errors (eg. connection
reset by peer), go make a cup of tea and come back in ten minutes.

### Loading SRA Data

Once the scheduler's up.  Assuming you have an SraRunInfo.csv file, and you've successfully
connected, you can load it with curl

    $ curl -s -X POST -T /path/to/SraRunInfo.csv localhost:8000/jobs/add_sra_run_info/

This should respond with a short JSON indicating the number of rows inserted, and the total
number in the scheduler.

In your web browser, refresh the status page.  You should now see a list of accessions by
state.  If ASGs are online, they should start processing immediately.  In a few seconds,
the first entry will switch to "splitting" state, which means it's working.

