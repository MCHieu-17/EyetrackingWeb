# k6 summary

scenario: lesson_contents

- http_req_waiting: p(99)=21.327, avg=12.057, min=2.842, med=12.142, max=21.812, p(90)=18.709, p(95)=19.382
- http_req_failed: rate=0.000
- http_req_connecting: max=0.101, p(90)=0.000, p(95)=0.000, p(99)=0.096, avg=0.002, min=0.000, med=0.000
- http_req_receiving: min=0.010, med=0.069, max=0.835, p(90)=0.228, p(95)=0.277, p(99)=0.346, avg=0.104
- http_req_blocked: max=0.378, p(90)=0.013, p(95)=0.018, p(99)=0.167, avg=0.016, min=0.003, med=0.011
- http_req_tls_handshaking: p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000
- http_req_duration: p(90)=18.861, p(95)=19.517, p(99)=21.533, avg=12.205, min=2.895, med=12.305, max=21.986
- http_req_duration{expected_response:true}: min=2.895, med=12.305, max=21.986, p(90)=18.861, p(95)=19.517, p(99)=21.533, avg=12.205
- iterations: rate=23.342, count=238.000
- vus: min=5.000, max=5.000
- http_req_sending: avg=0.043, min=0.008, med=0.040, max=0.779, p(90)=0.051, p(95)=0.062, p(99)=0.131
