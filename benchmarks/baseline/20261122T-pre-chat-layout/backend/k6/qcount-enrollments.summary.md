# k6 summary

scenario: enrollments

- http_req_duration: avg=4.032, min=1.108, med=4.300, max=4.842, p(90)=4.496, p(95)=4.535, p(99)=4.781
- http_req_receiving: avg=0.151, min=0.031, med=0.117, max=0.838, p(90)=0.174, p(95)=0.243, p(99)=0.719
- http_req_failed: rate=0.000
- http_req_waiting: med=4.122, max=4.352, p(90)=4.305, p(95)=4.344, p(99)=4.350, avg=3.838, min=1.051
- http_req_duration{expected_response:true}: p(99)=4.781, avg=4.032, min=1.108, med=4.300, max=4.842, p(90)=4.496, p(95)=4.535
- http_req_blocked: max=0.116, p(90)=0.013, p(95)=0.024, p(99)=0.098, avg=0.017, min=0.004, med=0.011
- vus: min=1.000, max=1.000
- http_req_sending: p(99)=0.087, avg=0.043, min=0.012, med=0.041, max=0.089, p(90)=0.051, p(95)=0.079
- iterations: count=20.000, rate=4.876
- http_req_connecting: p(95)=0.004, p(99)=0.070, avg=0.004, min=0.000, med=0.000, max=0.086, p(90)=0.000
- http_req_tls_handshaking: min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000
