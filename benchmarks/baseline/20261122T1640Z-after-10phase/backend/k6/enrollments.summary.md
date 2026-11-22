# k6 summary

scenario: enrollments

- http_req_failed: rate=0.000
- iterations: count=243.000, rate=24.034
- http_req_tls_handshaking: p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000
- vus: min=5.000, max=5.000
- http_req_receiving: avg=0.136, min=0.008, med=0.120, max=0.842, p(90)=0.240, p(95)=0.297, p(99)=0.616
- http_req_sending: max=2.026, p(90)=0.049, p(95)=0.063, p(99)=1.932, avg=0.077, min=0.007, med=0.039
- http_req_duration{expected_response:true}: p(99)=64.698, avg=6.058, min=1.039, med=4.398, max=83.024, p(90)=6.904, p(95)=7.306
- http_req_blocked: max=2.908, p(90)=0.013, p(95)=0.020, p(99)=1.219, avg=0.047, min=0.002, med=0.011
- http_req_connecting: p(90)=0.000, p(95)=0.000, p(99)=0.306, avg=0.006, min=0.000, med=0.000, max=0.329
- http_req_duration: max=83.024, p(90)=6.904, p(95)=7.306, p(99)=64.698, avg=6.058, min=1.039, med=4.398
- http_req_waiting: min=0.993, med=4.217, max=81.065, p(90)=6.685, p(95)=7.060, p(99)=62.715, avg=5.845
