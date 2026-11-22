# k6 summary

scenario: enrollments

- http_req_waiting: avg=4.171, min=2.805, med=4.212, max=4.465, p(90)=4.449, p(95)=4.458, p(99)=4.463
- http_req_connecting: avg=0.004, min=0.000, med=0.000, max=0.076, p(90)=0.000, p(95)=0.004, p(99)=0.061
- http_req_receiving: p(99)=0.279, avg=0.140, min=0.055, med=0.131, max=0.296, p(90)=0.186, p(95)=0.210
- http_req_duration{expected_response:true}: p(90)=4.629, p(95)=4.662, p(99)=4.673, avg=4.354, min=2.938, med=4.390, max=4.676
- http_req_duration: med=4.390, max=4.676, p(90)=4.629, p(95)=4.662, p(99)=4.673, avg=4.354, min=2.938
- http_req_tls_handshaking: max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000
- iterations: count=20.000, rate=4.868
- http_req_failed: rate=0.000
- http_req_blocked: p(90)=0.015, p(95)=0.043, p(99)=0.120, avg=0.019, min=0.008, med=0.011, max=0.140
- http_req_sending: avg=0.043, min=0.027, med=0.042, max=0.061, p(90)=0.050, p(95)=0.058, p(99)=0.060
- vus: max=1.000, min=1.000
