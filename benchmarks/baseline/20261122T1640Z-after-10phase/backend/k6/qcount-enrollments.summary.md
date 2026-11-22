# k6 summary

scenario: enrollments

- vus: min=1.000, max=1.000
- http_req_duration: min=4.043, med=4.511, max=4.806, p(90)=4.682, p(95)=4.690, p(99)=4.783, avg=4.449
- http_req_duration{expected_response:true}: min=4.043, med=4.511, max=4.806, p(90)=4.682, p(95)=4.690, p(99)=4.783, avg=4.449
- http_req_failed: rate=0.000
- http_req_receiving: max=0.194, p(90)=0.167, p(95)=0.178, p(99)=0.191, avg=0.128, min=0.039, med=0.117
- http_req_sending: avg=0.045, min=0.026, med=0.042, max=0.069, p(90)=0.056, p(95)=0.058, p(99)=0.067
- iterations: count=20.000, rate=4.862
- http_req_blocked: max=0.108, p(90)=0.017, p(95)=0.024, p(99)=0.091, avg=0.017, min=0.010, med=0.012
- http_req_waiting: max=4.604, p(90)=4.446, p(95)=4.525, p(99)=4.588, avg=4.276, min=3.927, med=4.347
- http_req_tls_handshaking: min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000
- http_req_connecting: min=0.000, med=0.000, max=0.081, p(90)=0.000, p(95)=0.004, p(99)=0.066, avg=0.004
