from django.core.management.base import BaseCommand
from django.contrib.auth.hashers import get_hasher
from django.utils.crypto import get_random_string
from os import urandom

from django_pph.shamirsecret import ShamirSecret
from django_pph.settings import SETTINGS
from django_pph.utils import bin64enc, binary_type


class Command(BaseCommand):

    help = 'Initializes a pph store'
    hasher = get_hasher('pph')

    def handle(self, *args, **options):

        # intialize the whole store, basically generate the secret, create
        # a shamir secret object and assign the secret to the thresholdlesskey
        self.hasher.data['secret'] = secret = self.create_secret()
        assert self.hasher.verify_secret(secret) is True
        self.hasher.update(
            shamirsecretobj=ShamirSecret(self.hasher.threshold, secret),
            thresholdlesskey=secret,
            secret=secret,
            nextavailableshare=1,
            is_unlocked=True,
        )

    def create_secret(self):
        """
        Returns a random string consisting of secret_length bytes of random
        data and verification_length bytes of hash to verify the secret upon
        recombination
        """
        secret_length = SETTINGS['SECRET_LENGTH']
        verification_len = SETTINGS['SECRET_VERIFICATION_BYTES']
        verification_iterations = SETTINGS['SECRET_ITERATIONS']

        secret = urandom(secret_length - verification_len)

        secret_digest = self.hasher.digest(secret, '', 1)
        for i in range(1, verification_iterations):
            secret_digest = self.hasher.digest(secret_digest, '', 1)
        secret_digest = bin64enc(secret_digest)

        secret += binary_type(secret_digest[:verification_len])
        return binary_type(secret)
